import os
import shutil
import subprocess
import tempfile
from pathlib import Path


class DocumentConversionError(RuntimeError):
    pass


def find_libreoffice():
    configured = os.getenv("LIBREOFFICE_BINARY", "").strip()
    candidates = [configured, "soffice", "libreoffice"]
    for candidate in candidates:
        if not candidate:
            continue
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
        if Path(candidate).is_file():
            return candidate
    return None


def libreoffice_available():
    return find_libreoffice() is not None


def convert_docx_bytes_to_pdf(docx_bytes, *, timeout=120):
    """Converte o DOCX final para PDF usando o mesmo motor de layout do Writer.

    Não existe fallback em ReportLab: reconstruir o PDF separadamente destruiria
    tabelas, cabeçalhos, rodapés, cores, quebras de página e demais propriedades do
    modelo enviado pelo usuário.
    """

    binary = find_libreoffice()
    if not binary:
        raise DocumentConversionError(
            "A conversão fiel para PDF requer LibreOffice no servidor. "
            "Publique o serviço com o Dockerfile do projeto ou configure "
            "LIBREOFFICE_BINARY para um executável válido."
        )

    with tempfile.TemporaryDirectory(prefix="ajudai-pdf-") as temp_directory:
        root = Path(temp_directory)
        source = root / "documento.docx"
        output = root / "documento.pdf"
        profile = root / "lo-profile"
        source.write_bytes(bytes(docx_bytes))
        profile.mkdir(parents=True, exist_ok=True)

        command = [
            binary,
            "--headless",
            "--nologo",
            "--nodefault",
            "--nolockcheck",
            f"-env:UserInstallation=file://{profile}",
            "--convert-to",
            "pdf:writer_pdf_Export",
            "--outdir",
            str(root),
            str(source),
        ]
        process = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
            env={**os.environ, "HOME": str(root)},
        )
        if process.returncode != 0 or not output.exists() or output.stat().st_size == 0:
            diagnostic = (process.stderr or process.stdout or "erro desconhecido").strip()
            raise DocumentConversionError(
                "O LibreOffice não conseguiu converter o DOCX para PDF: "
                + diagnostic[:600]
            )
        return output.read_bytes()
