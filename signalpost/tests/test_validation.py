import unittest

from signalpost.validation import OrganisationNumberError, validate_organisation_number


class OrganisationNumberTests(unittest.TestCase):
    def test_validates_display_form_and_normalises(self):
        self.assertEqual(validate_organisation_number("923 609 016"), "923609016")

    def test_rejects_bad_check_digit(self):
        with self.assertRaises(OrganisationNumberError):
            validate_organisation_number("923609017")

    def test_rejects_non_digits_and_boolean(self):
        for value in ("123", "ABCDEFGHI", True, None):
            with self.subTest(value=value):
                with self.assertRaises(OrganisationNumberError):
                    validate_organisation_number(value)


if __name__ == "__main__":
    unittest.main()
