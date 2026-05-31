

from src.services.qr_service import QRService


class TestQRServiceShortCode:
    def test_default_length(self):
        svc = QRService()
        code = svc.make_short_code()
        assert len(code) == 8

    def test_custom_length(self):
        svc = QRService()
        assert len(svc.make_short_code(12)) == 12

    def test_only_alphanumeric(self):
        svc = QRService()
        for _ in range(100):
            code = svc.make_short_code()
            assert code.isalnum(), f"Non-alphanumeric character in {code!r}"

    def test_uniqueness_high_probability(self):
        svc = QRService()
        codes = {svc.make_short_code() for _ in range(500)}
      
        assert len(codes) >= 490


class TestQRServicePNG:
    def test_generates_png_bytes(self):
        svc = QRService()
        result = svc.generate_png("https://example.com")
        assert isinstance(result, bytes)
        assert len(result) > 0
    
        assert result[:4] == b"\x89PNG"

    def test_different_error_corrections(self):
        svc = QRService()
        for ec in ("L", "M", "Q", "H"):
            data = svc.generate_png("https://example.com", error_correction=ec)
            assert data[:4] == b"\x89PNG"

    def test_custom_colors(self):
        svc = QRService()
        data = svc.generate_png(
            "https://example.com",
            fill_color="#1a1a2e",
            back_color="#e8e8ed",
        )
        assert data[:4] == b"\x89PNG"

    def test_large_box_size(self):
        svc = QRService()
        data = svc.generate_png("https://example.com", box_size=25, border=2)
        assert len(data) > 1000  

    def test_png_size_increases_with_box_size(self):
        svc = QRService()
        small = svc.generate_png("https://x.com", box_size=4)
        large = svc.generate_png("https://x.com", box_size=20)
        assert len(large) > len(small)


class TestQRServiceColorValidation:
    def test_valid_hex(self):
        svc = QRService()
        assert svc.validate_hex_color("#000000") is True
        assert svc.validate_hex_color("#FFFFFF") is True
        assert svc.validate_hex_color("#7c6af7") is True

    def test_invalid_hex_no_hash(self):
        svc = QRService()
        assert svc.validate_hex_color("000000") is False

    def test_invalid_hex_short(self):
        svc = QRService()
        assert svc.validate_hex_color("#fff") is False

    def test_invalid_hex_chars(self):
        svc = QRService()
        assert svc.validate_hex_color("#GGGGGG") is False
