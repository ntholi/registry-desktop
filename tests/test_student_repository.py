import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from database import Sponsor
from features.sync.students.repository import StudentRepository


class StudentRepositorySponsorTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Sponsor.__table__.create(self.engine)

        self.repository = StudentRepository()
        self.repository._engine = self.engine
        self.repository.clear_sponsor_cache()

    def tearDown(self):
        self.repository.clear_sponsor_cache()
        self.engine.dispose()

    def _insert_sponsor(self, *, name: str, code: str) -> int:
        with Session(self.engine) as session:
            sponsor = Sponsor(name=name, code=code)
            session.add(sponsor)
            session.commit()
            session.refresh(sponsor)
            return sponsor.id

    def test_lookup_sponsor_matches_existing_name_when_code_differs(self):
        sponsor_id = self._insert_sponsor(name="Self Sponsor", code="SELF")

        resolved_id = self.repository.lookup_sponsor("Self Sponsor")

        self.assertEqual(resolved_id, sponsor_id)

    def test_create_sponsor_reuses_existing_name_instead_of_creating_duplicate(self):
        sponsor_id = self._insert_sponsor(name="Self Sponsor", code="SELF")

        resolved_id = self.repository.create_sponsor("Self Sponsor")

        self.assertEqual(resolved_id, sponsor_id)

        with Session(self.engine) as session:
            sponsors = session.query(Sponsor.id, Sponsor.name, Sponsor.code).all()

        self.assertEqual(len(sponsors), 1)
        self.assertEqual(sponsors[0].id, sponsor_id)
        self.assertEqual(sponsors[0].name, "Self Sponsor")
        self.assertEqual(sponsors[0].code, "SELF")


if __name__ == "__main__":
    unittest.main()
