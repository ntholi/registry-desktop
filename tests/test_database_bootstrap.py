import unittest
from unittest.mock import Mock, patch

from database.bootstrap import (
    bootstrap_database,
    parse_country_selection,
    prompt_for_country_selection,
)


class DatabaseBootstrapTests(unittest.TestCase):
    def test_parse_country_selection_accepts_index_code_and_label(self):
        first_choice = parse_country_selection("1")
        country_code = parse_country_selection("eswatini")
        country_label = parse_country_selection("Lesotho")
        third_choice = parse_country_selection("3")

        if first_choice is None:
            self.fail("Expected indexed selection to resolve to a country")
        if country_code is None:
            self.fail("Expected country code selection to resolve to a country")
        if country_label is None:
            self.fail("Expected country label selection to resolve to a country")
        if third_choice is None:
            self.fail("Expected the third indexed selection to resolve to a country")
        self.assertEqual(first_choice.code, "lesotho")
        self.assertEqual(country_code.code, "eswatini")
        self.assertEqual(country_label.code, "lesotho")
        self.assertEqual(third_choice.code, "botswana")
        self.assertIsNone(parse_country_selection(""))

    def test_prompt_for_country_selection_retries_until_valid(self):
        responses = iter(["zambia", "2"])
        outputs: list[str] = []

        selected_country = prompt_for_country_selection(
            input_func=lambda _: next(responses),
            output_func=outputs.append,
        )

        self.assertEqual(selected_country.code, "eswatini")
        self.assertIn("1. Lesotho (cms_lesotho)", outputs)
        self.assertIn("2. Eswatini (cms_eswatini)", outputs)
        self.assertIn("3. Botswana (cms_botswana)", outputs)
        self.assertTrue(any("Invalid selection." in line for line in outputs))

    def test_bootstrap_database_configures_selected_country(self):
        engine = Mock()

        with (
            patch(
                "database.bootstrap.configure_database_urls_for_country"
            ) as configure,
            patch(
                "database.bootstrap.get_database_url",
                return_value="postgresql://user:pass@localhost:5432/cms_eswatini",
            ),
            patch(
                "database.bootstrap.ensure_database_exists",
                return_value=True,
            ) as ensure_exists,
            patch("database.bootstrap.create_database_engine", return_value=engine),
            patch("database.bootstrap.ensure_database_schema") as ensure_schema,
            patch("database.bootstrap.get_database_env_label", return_value="local"),
        ):
            result = bootstrap_database(
                admin_database="postgres",
                country_code="eswatini",
            )

        configure.assert_called_once_with("eswatini")
        self.assertEqual(ensure_exists.call_args.args[0].database, "cms_eswatini")
        self.assertEqual(ensure_exists.call_args.args[1], "postgres")
        ensure_schema.assert_called_once_with(engine)
        engine.dispose.assert_called_once()
        self.assertEqual(result.environment, "local")
        self.assertEqual(result.database_name, "cms_eswatini")
        self.assertTrue(result.database_created)
