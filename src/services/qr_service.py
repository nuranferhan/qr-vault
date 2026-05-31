
import io
import random
import string

import qrcode
from qrcode.constants import (
    ERROR_CORRECT_H,
    ERROR_CORRECT_L,
    ERROR_CORRECT_M,
    ERROR_CORRECT_Q,
)

try:
    from qrcode.image.styledimage import StyledPilImage
    from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer
    STYLED_AVAILABLE = True
except ImportError:
    STYLED_AVAILABLE = False

EC_MAP = {
    "L": ERROR_CORRECT_L,
    "M": ERROR_CORRECT_M,
    "Q": ERROR_CORRECT_Q,
    "H": ERROR_CORRECT_H,
}

_ALPHABET = string.ascii_letters + string.digits


class QRService:


    def make_short_code(self, length: int = 8) -> str:
        return "".join(random.choices(_ALPHABET, k=length))

    def generate_png(
        self,
        url: str,
        error_correction: str = "H",
        box_size: int = 10,
        border: int = 4,
        fill_color: str = "#000000",
        back_color: str = "#FFFFFF",
        rounded: bool = False,
    ) -> bytes:
        
        ec = EC_MAP.get(error_correction.upper(), ERROR_CORRECT_H)

        qr = qrcode.QRCode(
            version=None,  # auto-size
            error_correction=ec,
            box_size=box_size,
            border=border,
        )
        qr.add_data(url)
        qr.make(fit=True)

        if rounded and STYLED_AVAILABLE:
            img = qr.make_image(
                image_factory=StyledPilImage,
                module_drawer=RoundedModuleDrawer(),
                fill_color=fill_color,
                back_color=back_color,
            )
        else:
            img = qr.make_image(fill_color=fill_color, back_color=back_color)

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def validate_hex_color(self, color: str) -> bool:
        if not color.startswith("#") or len(color) != 7:
            return False
        try:
            int(color[1:], 16)
            return True
        except ValueError:
            return False