"""Read PDFs without mistaking owner restrictions for an opening password.

The original is never rewritten. Passwords exist only in the caller's memory.
"""
import io


class PDFPasswordRequired(ValueError):
    pass


def open_reader(raw, password=''):
    try:
        from pypdf import PdfReader
        from pypdf.errors import DependencyError
    except ImportError:
        raise ValueError('PDF-Lesen fehlt. Bitte EINRICHTEN_WINDOWS.bat erneut ausführen.') from None
    try:
        reader = PdfReader(io.BytesIO(raw))
        # is_encrypted remains True even after successful decrypt().
        if reader.is_encrypted and not reader.decrypt(password):
            raise PDFPasswordRequired('Dieses PDF benötigt ein Öffnungskennwort. Bitte das Kennwort eingeben und erneut lesen lassen.')
        len(reader.pages)
        return reader
    except PDFPasswordRequired:
        raise
    except DependencyError:
        raise ValueError('Für dieses PDF fehlt die Verschlüsselungs-Unterstützung. Bitte EINRICHTEN_WINDOWS.bat erneut ausführen.') from None
    except Exception:
        raise ValueError('Das PDF konnte nicht geöffnet werden. Bitte die Datei im PDF-Reader prüfen oder erneut von der Bank herunterladen.') from None
