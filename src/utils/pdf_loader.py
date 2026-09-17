import io
from pypdf import PdfReader
from src.common.custom_exception import CustomException
from src.common.logger import get_logger

logger = get_logger(__name__)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extracts raw text content from PDF binary data.

    Args:
        file_bytes: Binary buffer of the uploaded PDF file.

    Returns:
        Extracted text as a clean string.

    Raises:
        CustomException: If parsing fails or the document is unreadable.
    """
    try:
        reader = PdfReader(io.BytesIO(file_bytes))

        # Check for encrypted or password-protected PDF
        if reader.is_encrypted:
            try:
                # Attempt to decrypt with empty string for read-only permission locks
                if reader.decrypt("") == 0:
                    raise CustomException(
                        "PDF is password-protected or restricted. "
                        "Please switch to 'Plain Text / Bio' mode and paste your resume content directly.",
                        None,
                    )
            except Exception as dec_err:
                raise CustomException(
                    "PDF is encrypted or restricted. "
                    "Please switch to 'Plain Text / Bio' mode and paste your resume content directly.",
                    dec_err,
                )

        extracted_pages = []
        for index, page in enumerate(reader.pages):
            try:
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    extracted_pages.append(page_text.strip())
            except Exception as page_err:
                logger.warning(f"Could not extract text from page {index + 1}: {str(page_err)}")
                continue

        full_text = "\n\n".join(extracted_pages).strip()

        # Handle image-only, scanned, or non-standard font encoding
        if not full_text:
            raise CustomException(
                "No selectable text found in the PDF. This usually happens if the PDF is a scanned image, "
                "exported without a selectable text layer, or uses unsupported custom fonts. "
                "Please switch to 'Plain Text / Bio' mode above and paste your resume text directly.",
                None,
            )

        logger.info(f"Successfully extracted {len(extracted_pages)} pages from PDF.")
        return full_text

    except CustomException:
        raise
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        raise CustomException(
            f"Failed to parse PDF document ({str(e)}). "
            "The file may be corrupted or in an unsupported format. "
            "Please switch to 'Plain Text / Bio' mode and paste your resume text directly.",
            e,
        )