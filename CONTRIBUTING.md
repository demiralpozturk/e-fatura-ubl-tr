# Katkıda bulunma / Contributing

Teşekkürler! / Thank you for helping.

## Geliştirme ortamı / Development setup

```bash
git clone https://github.com/demiralpozturk/e-fatura-ubl-tr.git
cd e-fatura-ubl-tr
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
efatura schemas fetch            # GİB XSD + schematron (runtime download, not committed)
```

## Kontroller / Checks

```bash
pytest                 # GİB paketi önbellekte yoksa gerçek-şema testleri atlanır
ruff check .
ruff format .
mypy
```

`EFATURA_REQUIRE_GIB=1 pytest` ile GİB paketi olmadan testlerin atlanması yerine başarısız olması sağlanır (CI bunu kullanır).

## Kurallar / Rules

- **Gerçek kişi veya firma verisi eklemeyin.** Örneklerde kurgusal adlar ve checksum'ı geçen sentetik
  VKN/TCKN kullanın (`efatura_ubl_tr.identifiers.vkn_check_digit` / `tckn_check_digits`).
  Never add real personal or company data; use fictional names and synthetic IDs.
- **GİB dosyalarını depoya eklemeyin** (XSD, schematron, örnek XML, XSLT, logolar). Bkz. `docs/gib-files.md`.
  Do not commit GİB's files.
- Yeni bir fatura tipi veya alan eklerken örnek JSON ekleyin ve GİB doğrulamasından geçtiğini gösterin.
  New invoice types/fields need an example that passes GİB validation.
- Commit mesajları İngilizce ve [Conventional Commits](https://www.conventionalcommits.org/) biçiminde
  (`feat: …`, `fix: …`, `docs: …`, `test: …`).
- Hesaplama davranışını değiştiren her değişiklik `calc.py` belgelerini ve README'deki kuralları güncellemelidir.

## Hata bildirimi / Reporting issues

Lütfen mümkünse en küçük örnek JSON/XML'i ve `efatura validate --json` çıktısını ekleyin. Gerçek fatura
paylaşmayın; kişisel ve ticari bilgileri anonimleştirin.
