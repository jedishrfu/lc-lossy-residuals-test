"""Check recursive SDR selection and PATH fallback without installed codecs."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from benchmark_common import discover_inputs, executable, dataset_label, REPORT_ROOT, lc_source_dir
import lc_lossless_compress as runner


class DiscoveryTests(unittest.TestCase):
    def test_directory_patterns_extensions_and_deduplication(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            for name in ['HACC/a.f32', 'HACC/nested/a.f32.dat', 'NYX/a.f32', 'HACC/no.f64']:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b'abcd')
            selected = discover_inputs(['HACC', 'a.f32.dat'], root)
            self.assertEqual(len(selected), 2)
            self.assertEqual(len(discover_inputs([], root)), 3)
            self.assertNotEqual(dataset_label(selected[0]), dataset_label(selected[1]))
            with self.assertRaisesRegex(ValueError, 'No .f32'):
                discover_inputs(['missing'], root)
            selected[0].write_bytes(b'x')
            with self.assertRaisesRegex(ValueError, 'divisible by 4'):
                discover_inputs(['HACC'], root)

    def test_parallel_command_and_serial_fallback(self):
        with patch('benchmark_common.shutil.which', side_effect=lambda name: '/bin/'+name):
            self.assertEqual(executable('bzip2', ('pbzip2', 'lbzip2')), 'pbzip2')
        with patch('benchmark_common.shutil.which', side_effect=lambda name: '/bin/bzip2' if name == 'bzip2' else None):
            self.assertEqual(executable('bzip2', ('pbzip2', 'lbzip2')), 'bzip2')
        with patch('benchmark_common.shutil.which', return_value=None):
            with self.assertRaises(ValueError):
                executable('bzip2')

    def test_installed_pfpl_and_fpcompress_names(self):
        with tempfile.TemporaryDirectory() as directory:
            inp = Path(directory) / 'data.f32'
            inp.write_bytes(b'abcd')
            args = runner.build_parser().parse_args([str(inp), '--tools', 'pfpl', 'spspeed', 'spratio'])
            installed = {'pfpl-f32-abs_compress_omp', 'pfpl-f32-abs_decompress_omp',
                         'pfpl-f32-abs_compress_ser', 'pfpl-f32-abs_decompress_ser',
                         'fpcompress-single-speed-cpu-compress', 'fpcompress-single-speed-cpu-decompress',
                         'fpcompress-single-ratio-cpu-compress', 'fpcompress-single-ratio-cpu-decompress'}
            with patch('benchmark_common.shutil.which', side_effect=lambda name: '/bin/'+name if name in installed else None):
                runner.validate(args)
            self.assertEqual(args.pfpl_compressor, 'pfpl-f32-abs_compress_omp')
            self.assertEqual(args.pfpl_decompressor, 'pfpl-f32-abs_decompress_omp')
            self.assertEqual(args.spspeed_compressor, 'fpcompress-single-speed-cpu-compress')
            self.assertEqual(args.spratio_decompressor, 'fpcompress-single-ratio-cpu-decompress')

    def test_report_defaults_use_workspace(self):
        import lc_two_part_compress as sweep
        expected = Path(__file__).resolve().parents[2] / 'testrpts'
        self.assertEqual(REPORT_ROOT, expected)
        args = runner.build_parser().parse_args(['HACC'])
        self.assertEqual(Path(args.csv), expected / 'lossless_results.csv')
        args = sweep.build_parser().parse_args(['HACC'])
        self.assertEqual(Path(args.lossless_csv), expected / 'lossless_results.csv')

    def test_defaults_are_command_names(self):
        args = runner.build_parser().parse_args(['HACC'])
        for name in ('sleek_compressor', 'sleek_decompressor', 'spspeed_compressor',
                     'spratio_compressor', 'pfpl_compressor'):
            self.assertNotIn('/', getattr(args, name))

    def test_all_codec_commands_match_installed_names(self):
        import lc_two_part_compress as sweep
        installed = set("""lc sz3 zfp bzip2 zstd
            pfpl-f32-abs_compress_omp pfpl-f32-abs_decompress_omp
            sleek_single_compressor_lossless_cpu sleek_single_decompressor_lossless_cpu
            fpcompress-single-speed-cpu-compress fpcompress-single-speed-cpu-decompress
            fpcompress-single-ratio-cpu-compress fpcompress-single-ratio-cpu-decompress
            zip unzip g++""".split())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inp = root / 'test.f32'
            inp.write_bytes(b'abcd')
            (root / 'generate_standalone_CPU_compressor_decompressor.py').touch()
            args = runner.build_parser().parse_args([str(inp), '--lc-dir', str(root), '--compiler', 'g++'])
            with patch('benchmark_common.shutil.which', side_effect=lambda name: '/bin/'+name if name in installed else None):
                runner.validate(args)
            self.assertEqual(args.lc, 'lc')
            for tool in runner.TOOLS:
                if tool == 'lc':
                    continue
                encode, decode, *_ = runner.commands(args, tool, inp, root/'compressed', root/'decoded', 1)
                self.assertIn(encode[0], installed)
                self.assertIn(decode[0], installed)
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(runner.build_parser().parse_args(['HACC']).compiler, 'g++')
            self.assertEqual(sweep.build_parser().parse_args(['HACC']).compiler, 'g++')

    def test_lc_sources_found_in_workspace_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            binary = workspace / 'bin' / 'lc'
            binary.parent.mkdir()
            binary.touch()
            sources = workspace / 'github' / 'LC-framework'
            sources.mkdir(parents=True)
            generator = sources / 'generate_standalone_CPU_compressor_decompressor.py'
            generator.touch()
            with patch('benchmark_common.shutil.which', return_value=str(binary)):
                self.assertEqual(lc_source_dir(None, 'lc'), sources)
                self.assertEqual(lc_source_dir(str(workspace / 'custom'), 'lc'), workspace / 'custom')
                (binary.parent / generator.name).touch()
                self.assertEqual(lc_source_dir(None, 'lc'), binary.parent)

    def test_missing_lc_sources_give_actionable_error(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('benchmark_common.shutil.which', return_value=str(Path(directory)/'bin/lc')), patch('benchmark_common.__file__', str(Path(directory)/'projects/benchmark/benchmark_common.py')):
                with self.assertRaisesRegex(ValueError, '--lc-dir'):
                    lc_source_dir(None, 'lc')
