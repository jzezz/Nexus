import asyncio
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import store
from app.models import Base
from app.services.ingestion import ingest_document, sanitize_filename
from app.services.orchestration import route_question, run_chat
from app.services.auth import register_user


class UploadStub:
    def __init__(self, filename: str, content: bytes) -> None:
        self.filename = filename
        self.content = content

    async def read(self) -> bytes:
        return self.content


class NexusMvpFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.user = register_user(self.db, "mvp@example.com", "password123")

    def tearDown(self) -> None:
        self.db.close()

    def test_document_question_is_retrieved_and_saved_with_citations(self) -> None:
        document = store.create_document(self.db, self.user.id, "launch-plan.csv", "csv", "")
        document = store.attach_chunks(
            self.db,
            document,
            [{
                "content": "The pilot launch is scheduled for 15 October with the first ten customers.",
                "chunk_index": 0,
                "page_number": 1,
                "token_count": 13,
                "keyword_signature": "pilot, launch, october, customers",
            }],
            "The pilot launch is scheduled for 15 October with the first ten customers.",
            1,
        )

        conversation_id, route, _answer, confidence, citations, scope = run_chat(
            self.db, self.user, "Which date is the pilot launch?", None, [document.id]
        )

        self.assertEqual(route, "retrieval")
        self.assertGreater(confidence, 0)
        self.assertEqual(citations[0]["document_id"], document.id)
        self.assertEqual(scope, [document.id])
        self.assertEqual(len(store.get_history(self.db, conversation_id)), 2)

    def test_unknown_scoped_document_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "selected documents"):
            run_chat(self.db, self.user, "Which document is selected?", None, ["missing-document"])

    def test_corrupt_upload_is_a_user_error_and_is_recorded_as_failed(self) -> None:
        with self.assertRaisesRegex(ValueError, "Could not extract readable text"):
            asyncio.run(ingest_document(self.db, self.user.id, UploadStub("broken.pdf", b"not a PDF")))

        document = store.list_documents(self.db, self.user.id)[0]
        self.assertEqual(document.status, "failed")
        self.assertFalse(document.retrieval_ready)

    def test_filename_sanitization_and_greeting_routing(self) -> None:
        self.assertEqual(sanitize_filename("../../brief?.pdf"), "brief_.pdf")
        self.assertEqual(route_question("Hi!", True), "direct")
        self.assertEqual(route_question("Which pilot date is listed?", True), "retrieval")


if __name__ == "__main__":
    unittest.main()
