"""Check recursive SDR selection and PATH fallback without installed codecs."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from benchmark_common import discover_inputs, executable, dataset_label, REPORT_ROOT
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
