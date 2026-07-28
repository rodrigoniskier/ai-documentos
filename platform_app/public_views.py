import io

from PIL import Image, ImageDraw, ImageFont
from django.http import HttpResponse
from django.utils.cache import patch_cache_control
from django.views.decorators.cache import cache_page


def _font(size: int, bold: bool = False):
    names = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


@cache_page(60 * 60 * 24)
def social_card(request):
    image = Image.new("RGB", (1200, 630), "#0B1F3A")
    draw = ImageDraw.Draw(image)
    for x in range(-200, 1400, 110):
        draw.line((x, 0, x + 360, 630), fill="#123154", width=2)

    draw.rounded_rectangle((70, 55, 410, 112), radius=24, fill="#FFC107")
    draw.text((94, 68), "AjudAI Docente", font=_font(28, bold=True), fill="#0B1F3A")
    draw.text((68, 164), "SEU MODELO.", font=_font(58, bold=True), fill="#FFFFFF")
    draw.text((68, 235), "SUAS REFERÊNCIAS.", font=_font(42, bold=True), fill="#FFC107")
    draw.text((68, 292), "SUA REVISÃO.", font=_font(42, bold=True), fill="#FFC107")
    draw.rounded_rectangle((70, 382, 615, 452), radius=32, fill="#FFFFFF")
    draw.text((100, 400), "DOCUMENTOS COM IA", font=_font(29, bold=True), fill="#0B1F3A")
    draw.text((72, 498), "Modelos próprios · editor revisável", font=_font(23), fill="#DCE7F3")
    draw.text((72, 532), "Exportação em DOCX e PDF", font=_font(23), fill="#DCE7F3")

    draw.rounded_rectangle((760, 80, 1115, 550), radius=30, fill="#FFFFFF")
    draw.rounded_rectangle((800, 130, 1075, 445), radius=20, fill="#F4F6F9")
    draw.text((842, 168), "MODELO DOCX", font=_font(24, bold=True), fill="#0B1F3A")
    draw.rectangle((834, 220, 1040, 232), fill="#2E74B5")
    for index, width in enumerate((200, 182, 216, 174, 198)):
        y = 270 + index * 34
        draw.rounded_rectangle((834, y, 834 + width, y + 11), radius=5, fill="#C8D3E1")
    draw.rounded_rectangle((833, 470, 1045, 520), radius=22, fill="#FFC107")
    draw.text((866, 481), "DOCX + PDF", font=_font(21, bold=True), fill="#0B1F3A")

    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    response = HttpResponse(output.getvalue(), content_type="image/png")
    patch_cache_control(response, public=True, max_age=86400, immutable=True)
    return response
