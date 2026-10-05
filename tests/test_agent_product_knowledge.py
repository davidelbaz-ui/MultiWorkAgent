"""Agent product knowledge injection."""

from __future__ import annotations

import unittest

import agent_executor


class AgentProductKnowledgeTest(unittest.TestCase):
    def test_product_knowledge_file_loads(self) -> None:
        text = agent_executor._load_product_knowledge()
        self.assertIn("MultiWorkAgent", text)
        self.assertIn("Execution runs", text)

    def test_system_prompt_includes_product_reference(self) -> None:
        prompt = agent_executor._system_prompt(
            scope_label="All businesses",
            business_name=None,
            knowledge_block=None,
        )
        self.assertIn("product reference", prompt.lower())
        self.assertIn("Starter", prompt)


if __name__ == "__main__":
    unittest.main()
