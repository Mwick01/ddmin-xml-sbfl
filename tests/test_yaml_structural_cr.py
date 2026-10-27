"""Regression checks for CR-preserving structural YAML deletions."""

import unittest

from yaml_structural_candidates import collect_deletions, parse_yaml, valid_yaml
from yaml_structural_ddmin import apply_deletions


SOURCE = (
    "blockText: |\r"
    "  some arbitrary text \r"
    "  spanning some \r"
    "  lines, that are split \r"
    "  by CR and NL\r"
    "followup: 1"
)


class StructuralCRTests(unittest.TestCase):
    def test_block_units_preserve_carriage_returns(self):
        operations = collect_deletions(SOURCE, parse_yaml(SOURCE))
        self.assertEqual(
            [operation.kind for operation in operations],
            ["block_mapping_entry"] * 2 + ["block_scalar_line"] * 4,
        )
        for operation in operations:
            candidate = apply_deletions(SOURCE, [operation])
            self.assertTrue(valid_yaml(candidate), operation.path)
            self.assertEqual(candidate, SOURCE[:operation.start] + SOURCE[operation.end:])

    def test_grouped_line_deletions_reparse_after_each_edit(self):
        operations = collect_deletions(SOURCE, parse_yaml(SOURCE))
        line_operations = [op for op in operations if op.kind == "block_scalar_line"]
        candidate = apply_deletions(SOURCE, line_operations)
        self.assertEqual(candidate, "blockText: |\rfollowup: 1")
        self.assertTrue(valid_yaml(candidate))


if __name__ == "__main__":
    unittest.main()
