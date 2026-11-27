"""Code lists used by UBL-TR invoices.

Values come from GİB's public *UBL-TR Kod Listeleri* guide (v1.43, July 2026) and
the code lists embedded in GİB's schematron package. Code values are facts needed
for interoperability; Turkish names are given for convenience. GİB updates these
lists from time to time, so the schematron validation (``efatura validate``)
always uses the *current* lists downloaded from GİB.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import NamedTuple

__all__ = [
    "CURRENCY_NAMES",
    "IHRACKAYITLI_EXEMPTION_CODES",
    "ISTISNA_EXEMPTION_CODES",
    "KDV_TAX_CODE",
    "OTHER_ZERO_KDV_CODES",
    "OZELMATRAH_CODES",
    "PAYMENT_MEANS_CODES",
    "SUPPORT_MATRIX",
    "TAX_TYPES",
    "UNIT_CODES",
    "WITHHOLDING_CODES",
    "InvoiceType",
    "Profile",
    "SupportLevel",
    "TaxType",
    "WithholdingCode",
    "exemption_reason_name",
]


class Profile(str, Enum):
    """``cbc:ProfileID`` – the e-Fatura scenario (senaryo)."""

    TEMELFATURA = "TEMELFATURA"
    TICARIFATURA = "TICARIFATURA"
    EARSIVFATURA = "EARSIVFATURA"

    @property
    def is_earsiv(self) -> bool:
        return self is Profile.EARSIVFATURA


class InvoiceType(str, Enum):
    """``cbc:InvoiceTypeCode`` – the invoice type (fatura tipi)."""

    SATIS = "SATIS"
    IADE = "IADE"
    TEVKIFAT = "TEVKIFAT"
    ISTISNA = "ISTISNA"
    IHRACKAYITLI = "IHRACKAYITLI"
    OZELMATRAH = "OZELMATRAH"


class SupportLevel(str, Enum):
    FULL = "full"
    EXPERIMENTAL = "experimental"


#: Which invoice types this library supports and how well.
SUPPORT_MATRIX: dict[InvoiceType, SupportLevel] = {
    InvoiceType.SATIS: SupportLevel.FULL,
    InvoiceType.IADE: SupportLevel.FULL,
    InvoiceType.TEVKIFAT: SupportLevel.FULL,
    InvoiceType.ISTISNA: SupportLevel.FULL,
    InvoiceType.IHRACKAYITLI: SupportLevel.EXPERIMENTAL,
    InvoiceType.OZELMATRAH: SupportLevel.EXPERIMENTAL,
}

#: KDV (Gerçek usulde katma değer vergisi) tax type code.
KDV_TAX_CODE = "0015"


class TaxType(NamedTuple):
    name: str
    short_name: str
    #: Whether :class:`~efatura_ubl_tr.models.LineTax` may use this code in v0.1.
    supported: bool


#: ``cbc:TaxTypeCode`` values (VERGİ KODLARI LİSTESİ).
TAX_TYPES: dict[str, TaxType] = {
    "0003": TaxType("Gelir Vergisi Stopajı", "GV STOPAJI", False),
    "0011": TaxType("Kurumlar Vergisi Stopajı", "KV STOPAJI", False),
    "0015": TaxType("Gerçek Usulde Katma Değer Vergisi", "KDV", False),
    "0021": TaxType("Banka Muameleleri Vergisi", "BMV", True),
    "0022": TaxType("Sigorta Muameleleri Vergisi", "SMV", True),
    "0059": TaxType("Konaklama Vergisi", "KONAKLAMA V", False),
    "0061": TaxType("Kaynak Kullanımı Destekleme Fonu Kesintisi", "KKDF KESİNTİ", True),
    "0071": TaxType(
        "Petrol ve Doğalgaz Ürünlerine İlişkin Özel Tüketim Vergisi", "ÖTV 1.LİSTE", True
    ),
    "0073": TaxType(
        "Kolalı Gazoz, Alkollü İçecekler ve Tütün Mamullerine İlişkin Özel Tüketim Vergisi",
        "ÖTV 3.LİSTE",
        True,
    ),
    "0074": TaxType(
        "Dayanıklı Tüketim ve Diğer Mallara İlişkin Özel Tüketim Vergisi", "ÖTV 4.LİSTE", True
    ),
    "0075": TaxType("Alkollü İçeceklere İlişkin Özel Tüketim Vergisi", "ÖTV 3A LİSTE", True),
    "0076": TaxType("Tütün Mamullerine İlişkin Özel Tüketim Vergisi", "ÖTV 3B LİSTE", True),
    "0077": TaxType("Kolalı Gazozlara İlişkin Özel Tüketim Vergisi", "ÖTV 3C LİSTE", True),
    "1047": TaxType("Damga Vergisi", "DAMGA V", True),
    "1048": TaxType("5035 Sayılı Kanuna Göre Damga Vergisi", "5035SKDAMGAV", True),
    "4071": TaxType("Elektrik ve Havagazı Tüketim Vergisi", "ELK.HAVAGAZ.TÜK.VER.", True),
    "4080": TaxType("Özel İletişim Vergisi", "Ö.İLETİŞİM V", True),
    "4081": TaxType("5035 Sayılı Kanuna Göre Özel İletişim Vergisi", "5035ÖZİLETV.", True),
    "4171": TaxType(
        "Petrol ve Doğalgaz Ürünlerine İlişkin ÖTV Tevkifatı", "PTR-DGZ ÖTV TEV", False
    ),
    "8001": TaxType("Borsa Tescil Ücreti", "BORSA TES.ÜC.", True),
    "8002": TaxType("Enerji Fonu", "ENERJİ FONU", True),
    "8004": TaxType("TRT Payı", "TRT PAYI", True),
    "8005": TaxType("Elektrik Tüketim Vergisi", "ELK.TÜK.VER.", True),
    "8006": TaxType("Telsiz Kullanım Ücreti", "TK KULLANIM", True),
    "8007": TaxType("Telsiz Ruhsat Ücreti", "TK RUHSAT", True),
    "8008": TaxType("Çevre Temizlik Vergisi", "ÇEV. TEM .VER.", True),
    "9021": TaxType("4961 Banka Sigorta Muameleleri Vergisi", "4961BANKASMV", True),
    "9040": TaxType("Mera Fonu", "MERA FONU", True),
    "9077": TaxType(
        "Motorlu Taşıt Araçlarına İlişkin Özel Tüketim Vergisi (Tescile Tabi Olanlar)",
        "ÖTV 2.LİSTE",
        True,
    ),
    "9944": TaxType("Belediyelere Ödenen Hal Rüsumu", "BEL.ÖD.HAL RÜSUM", True),
}


class WithholdingCode(NamedTuple):
    name: str
    #: Default rate in percent (e.g. 90 for "9/10").
    default_rate: Decimal
    #: Rates accepted by GİB's schematron for this code (percent).
    allowed_rates: tuple[Decimal, ...]


def _w(name: str, default: int, *others: int) -> WithholdingCode:
    rates = tuple(Decimal(r) for r in sorted({default, *others}))
    return WithholdingCode(name, Decimal(default), rates)


#: KDV tevkifat codes (``WithholdingTaxTotal/.../cbc:TaxTypeCode``).
WITHHOLDING_CODES: dict[str, WithholdingCode] = {
    "601": _w(
        "Yapım İşleri ile Bu İşlerle Birlikte İfa Edilen Mühendislik-Mimarlık ve Etüt-Proje "
        "Hizmetleri",
        40,
        30,
    ),
    "602": _w("Etüt, Plan-Proje, Danışmanlık, Denetim ve Benzeri Hizmetler", 90),
    "603": _w(
        "Makine, Teçhizat, Demirbaş ve Taşıtlara Ait Tadil, Bakım ve Onarım Hizmetleri", 70, 50
    ),
    "604": _w("Yemek Servis Hizmeti", 50),
    "605": _w("Organizasyon Hizmeti", 50),
    "606": _w("İşgücü Temin Hizmetleri", 90),
    "607": _w("Özel Güvenlik Hizmeti", 90),
    "608": _w("Yapı Denetim Hizmetleri", 90),
    "609": _w(
        "Fason Olarak Yaptırılan Tekstil ve Konfeksiyon İşleri, Çanta ve Ayakkabı Dikim İşleri "
        "ve Bu İşlere Aracılık Hizmetleri",
        70,
        50,
    ),
    "610": _w("Turistik Mağazalara Verilen Müşteri Bulma / Götürme Hizmetleri", 90),
    "611": _w("Spor Kulüplerinin Yayın, Reklam ve İsim Hakkı Gelirlerine Konu İşlemleri", 90),
    "612": _w("Temizlik Hizmeti", 90, 70),
    "613": _w("Çevre ve Bahçe Bakım Hizmetleri", 90, 70),
    "614": _w("Servis Taşımacılığı Hizmeti", 50),
    "615": _w("Her Türlü Baskı ve Basım Hizmetleri", 70, 50),
    "616": _w("Diğer Hizmetler", 50),
    "617": _w("Hurda Metalden Elde Edilen Külçe Teslimleri", 70),
    "618": _w(
        "Hurda Metalden Elde Edilenler Dışındaki Bakır, Çinko, Demir Çelik, Alüminyum ve "
        "Kurşun Külçe Teslimleri",
        70,
    ),
    "619": _w("Bakır, Çinko ve Alüminyum Ürünlerinin Teslimi", 70),
    "620": _w("İstisnadan Vazgeçenlerin Hurda ve Atık Teslimi", 70),
    "621": _w(
        "Metal, Plastik, Lastik, Kauçuk, Kâğıt ve Cam Hurda ve Atıklardan Elde Edilen "
        "Hammadde Teslimi",
        90,
    ),
    "622": _w("Pamuk, Tiftik, Yün ve Yapağı ile Ham Post ve Deri Teslimleri", 90),
    "623": _w("Ağaç ve Orman Ürünleri Teslimi", 50),
    "624": _w("Yük Taşımacılığı Hizmeti", 20),
    "625": _w("Ticari Reklam Hizmetleri", 30),
    "626": _w("Diğer Teslimler", 20),
    "627": _w("Demir-Çelik Ürünlerinin Teslimi", 50, 40),
    # Tam (10/10) tevkifat codes
    "801": _w(
        "Yapım İşleri ile Bu İşlerle Birlikte İfa Edilen Mühendislik-Mimarlık ve Etüt-Proje "
        "Hizmetleri (tam tevkifat)",
        100,
    ),
    "802": _w("Etüt, Plan-Proje, Danışmanlık, Denetim ve Benzeri Hizmetler (tam tevkifat)", 100),
    "803": _w(
        "Makine, Teçhizat, Demirbaş ve Taşıtlara Ait Tadil, Bakım ve Onarım Hizmetleri "
        "(tam tevkifat)",
        100,
    ),
    "804": _w("Yemek Servis Hizmeti (tam tevkifat)", 100),
    "805": _w("Organizasyon Hizmeti (tam tevkifat)", 100),
    "806": _w("İşgücü Temin Hizmetleri (tam tevkifat)", 100),
    "807": _w("Özel Güvenlik Hizmeti (tam tevkifat)", 100),
    "808": _w("Yapı Denetim Hizmetleri (tam tevkifat)", 100),
    "809": _w(
        "Fason Olarak Yaptırılan Tekstil ve Konfeksiyon İşleri, Çanta ve Ayakkabı Dikim İşleri "
        "ve Bu İşlere Aracılık Hizmetleri (tam tevkifat)",
        100,
    ),
    "810": _w("Turistik Mağazalara Verilen Müşteri Bulma / Götürme Hizmetleri (tam tevkifat)", 100),
    "811": _w(
        "Spor Kulüplerinin Yayın, Reklam ve İsim Hakkı Gelirlerine Konu İşlemleri (tam tevkifat)",
        100,
    ),
    "812": _w("Temizlik Hizmeti (tam tevkifat)", 100),
    "813": _w("Çevre ve Bahçe Bakım Hizmetleri (tam tevkifat)", 100),
    "814": _w("Servis Taşımacılığı Hizmeti (tam tevkifat)", 100),
    "815": _w("Her Türlü Baskı ve Basım Hizmetleri (tam tevkifat)", 100),
    "816": _w("Hurda Metalden Elde Edilen Külçe Teslimleri (tam tevkifat)", 100),
    "817": _w(
        "Hurda Metalden Elde Edilenler Dışındaki Bakır, Çinko, Demir Çelik, Alüminyum ve "
        "Kurşun Külçe Teslimi (tam tevkifat)",
        100,
    ),
    "818": _w("Bakır, Çinko, Alüminyum ve Kurşun Ürünlerinin Teslimi (tam tevkifat)", 100),
    "819": _w("İstisnadan Vazgeçenlerin Hurda ve Atık Teslimi (tam tevkifat)", 100),
    "820": _w(
        "Metal, Plastik, Lastik, Kauçuk, Kâğıt ve Cam Hurda ve Atıklardan Elde Edilen "
        "Hammadde Teslimi (tam tevkifat)",
        100,
    ),
    "821": _w("Pamuk, Tiftik, Yün ve Yapağı ile Ham Post ve Deri Teslimleri (tam tevkifat)", 100),
    "822": _w("Ağaç ve Orman Ürünleri Teslimi (tam tevkifat)", 100),
    "823": _w("Yük Taşımacılığı Hizmeti (tam tevkifat)", 100),
    "824": _w("Ticari Reklam Hizmetleri (tam tevkifat)", 100),
    "825": _w("Demir-Çelik Ürünlerinin Teslimi (tam tevkifat)", 100),
}

#: Exemption (istisna) codes allowed for the ISTISNA invoice type, with names.
ISTISNA_EXEMPTION_CODES: dict[str, str] = {
    "201": "17/1 Kültür ve Eğitim Amacı Taşıyan İşlemler",
    "202": "17/2-a Sağlık, Çevre ve Sosyal Yardım Amaçlı İşlemler",
    "204": "17/2-c Yabancı Diplomatik Organ ve Hayır Kurumlarının Bağışlarla İlgili Alışları",
    "205": "17/2-d Taşınmaz Kültür Varlıklarına İlişkin Teslimler ve Mimarlık Hizmetleri",
    "206": "17/2-e Mesleki Kuruluşların İşlemleri",
    "207": "17/3 Askeri Fabrika, Tersane ve Atölyelerin İşlemleri",
    "208": "17/4-c Birleşme, Devir, Dönüşüm ve Bölünme İşlemleri",
    "209": "17/4-e Banka ve Sigorta Muameleleri Vergisi Kapsamına Giren İşlemler",
    "211": "17/4-h Zirai Amaçlı Su Teslimleri ile Köy Tüzel Kişiliklerince İçme Suyu Teslimleri",
    "212": "17/4-ı Serbest Bölgelerde Verilen Hizmetler",
    "213": "17/4-j Boru Hattı ile Yapılan Petrol ve Gaz Taşımacılığı",
    "214": "17/4-k OSB Arsa ve İşyeri Teslimleri ile Konut Yapı Kooperatiflerinin Konut Teslimleri",
    "215": "17/4-l Varlık Yönetim Şirketlerinin İşlemleri",
    "216": "17/4-m Tasarruf Mevduatı Sigorta Fonunun İşlemleri",
    "217": "17/4-n Basın-Yayın ve Enformasyon Genel Müdürlüğüne Verilen Haber Hizmetleri",
    "218": "17/4-o Gümrük Antrepoları ve Gümrüklü Sahalardaki Bağımsız Birimlerin Kiralanması",
    "219": "Hazine, TOKİ, Belediyeler, İl Özel İdareleri ve YİKOB İşlemleri",
    "220": "17/4-r Taşınmaz ve İştirak Hissesi Satışları",
    "221": "Geçici 15 Konut Yapı Kooperatifleri, Belediyeler ve SGK'ya İnşaat Taahhüt Hizmeti",
    "223": "Geçici 20/1 Teknoloji Geliştirme Bölgelerinde Yapılan İşlemler",
    "225": "Geçici 23 Milli Eğitim Bakanlığına Yapılan Bilgisayar Bağışları ile İlgili Teslimler",
    "226": "17/2-b Özel Okul ve Üniversitelerin Bedelsiz Eğitim ve Öğretim Hizmetleri",
    "227": "17/2-b Kanunların Gösterdiği Gerek Üzerine Bedelsiz Teslim ve Hizmetler",
    "228": "17/2-b 17/1 Maddesinde Sayılan Kuruluşlara Bedelsiz Teslimler",
    "229": "Gıda Bankacılığı Kapsamında Bağışlanan Gıda, Temizlik, Giyecek ve Yakacak Maddeleri",
    "230": "17/4-g Külçe Altın, Külçe Gümüş ve Kıymetli Taşların Teslimi",
    "231": "17/4-g Metal, Plastik, Lastik, Kauçuk, Kâğıt, Cam Hurda ve Atıkların Teslimi",
    "232": "17/4-g Döviz, Para, Damga Pulu, Değerli Kâğıtlar, Hisse Senedi ve Tahvil Teslimleri",
    "233": "2942 Sayılı Kanun Kapsamında Taşınmazların Kamulaştırmayı Yapana Devri",
    "234": "17/4-ş Konut Finansmanı Amacıyla Teminat Gösterilen Konutların Teslimi",
    "235": "16/1-c Transit, Antrepo, Geçici Depolama ve Serbest Bölge Rejimindeki Mal Teslimi",
    "236": "19/2 Uluslararası Anlaşmalar Kapsamındaki İstisnalar (İade Hakkı Tanınmayan)",
    "237": "17/4-t Ürün Senetlerinin Borsalar Aracılığıyla İlk Teslimlerinden Sonraki Teslim",
    "238": "17/4-u Varlık Kiralama Şirketleri ile Yapılan Devir ve Kiralamalar",
    "239": "17/4-y Taşınmazların Finansal Kiralama Şirketlerine Devri ve Geri Kiralanması",
    "240": "17/4-z Patentli veya Faydalı Model Belgeli Buluşa İlişkin Hakların Devri",
    "241": "TürkAkım Gaz Boru Hattı Projesine İlişkin Anlaşmanın (9/b) Maddesindeki Hizmetler",
    "242": "17/4-ö Gümrüklü Sahalarda İthalat/İhracat Mallarına Ardiye ve Depolama Hizmetleri",
    "250": "Diğerleri (kısmi istisna)",
    "301": "11/1-a Mal İhracatı",
    "302": "11/1-a Hizmet İhracatı",
    "303": "11/1-a Roaming Hizmetleri",
    "304": "13/a Deniz, Hava ve Demiryolu Taşıma Araçlarının Teslimi ile İnşa, Tadil, Bakım ve "
    "Onarımları",
    "305": "13/b Deniz ve Hava Taşıma Araçları için Liman ve Hava Meydanlarında Yapılan Hizmetler",
    "306": "13/c Petrol Aramaları ve Petrol Boru Hatlarına İlişkin Teslim ve Hizmetler",
    "307": "13/c Maden Arama ve Altın, Gümüş, Platin Madenciliğine İlişkin Teslim ve Hizmetler",
    "308": "13/d Teşvikli Yatırım Mallarının Teslimi",
    "309": "13/e Liman ve Hava Meydanlarının İnşası, Yenilenmesi ve Genişletilmesi",
    "310": "13/f Ulusal Güvenlik Amaçlı Teslim ve Hizmetler",
    "311": "14/1 Uluslararası Taşımacılık",
    "312": "15/a Diplomatik Organ ve Misyonlara Yapılan Teslim ve Hizmetler",
    "313": "15/b Uluslararası Kuruluşlara Yapılan Teslim ve Hizmetler",
    "314": "19/2 Usulüne Göre Yürürlüğe Girmiş Uluslararası Anlaşmalar Kapsamındaki İstisnalar",
    "315": "14/3 İhraç Konusu Eşyayı Taşıyan Araçlara Yapılan Motorin Teslimleri",
    "316": "11/1-a Serbest Bölgelerdeki Müşteriler için Yapılan Fason Hizmetler",
    "317": "17/4-s Engellilere Yönelik Araç-Gereç ve Bilgisayar Programları",
    "318": "Geçici 29 Yap-İşlet-Devret ve Kiralama Karşılığı Projelere İlişkin Teslim ve Hizmetler",
    "319": "13/g Başbakanlık Merkez Teşkilatına Yapılan Araç Teslimleri",
    "320": "Geçici 16 İSMEP Kapsamında İstanbul Proje Koordinasyon Birimine Teslim ve Hizmetler",
    "321": "Geçici 26 BM, NATO ve OECD Temsilciliklerine Yapılan Teslim ve Hizmetler",
    "322": "11/1-a Türkiye'de İkamet Etmeyenlere Özel Fatura ile Yapılan Teslimler "
    "(Bavul Ticareti)",
    "323": "13/ğ Ürün Senetlerinin Borsalar Aracılığıyla İlk Teslimi",
    "324": "13/h Türkiye Kızılay Derneğine Yapılan ve Derneğin Yaptığı Teslim ve Hizmetler",
    "325": "13/ı Yem Teslimleri",
    "326": "13/ı Tescil Edilmiş Gübrelerin Teslimi",
    "327": "13/ı Gübre Hammaddelerinin Gübre Üreticilerine Teslimi",
    "328": "13/i Konut veya İşyeri Teslimleri",
    "329": "FATİH Projesi Kapsamında Milli Eğitim Bakanlığına Teslim ve Hizmetler",
    "330": "13/j Organize Sanayi Bölgeleri ile Küçük Sanayi Sitelerinin İnşasına İlişkin "
    "Teslim ve Hizmetler",
    "331": "13/m Ar-Ge, Yenilik ve Tasarım Faaliyetleri için Yeni Makine ve Teçhizat Teslimleri",
    "332": "Geçici 39 İmalat Sanayiinde Kullanılacak Yeni Makine ve Teçhizat Teslimleri",
    "333": "13/k Kamu İdarelerine Bağışlanan Tesislerin İnşasına İlişkin İstisna",
    "334": "13/l Yabancılara Verilen Sağlık Hizmetleri",
    "335": "13/n Basılı Kitap ve Süreli Yayınların Teslimleri",
    "336": "Geçici 46 UEFA Müsabakaları Kapsamında Teslim ve Hizmetler",
    "337": "TürkAkım Projesi (9/h) Kapsamındaki Gaz Taşıma Hizmetleri",
    "338": "İmalatçıların Mal İhracatları",
    "339": "İmalat Sanayii ile Turizme Yönelik Teşvik Belgeli İnşaat İşleri",
    "340": "Elektrik Motorlu Taşıt Araçlarının Geliştirilmesine Yönelik Mühendislik Hizmetleri",
    "341": "Afetzedelere Bağışlanacak Konutların İnşasına İlişkin İstisna",
    "342": "Genel Bütçeli Kamu İdarelerine Bağışlanacak Taşınmazların İnşasına İlişkin İstisna",
    "343": "Kamu İdarelerine Bağışlanacak Konutların Yabancı Devlet Kuruluşlarına Teslimi",
    "344": "13/o Milli Savunma ve İç Güvenlik İhtiyaçları için Taşıt Teslimi",
    "350": "Diğerleri",
}

#: Exemption codes that may appear on SATIS / TEVKIFAT invoices with a 0 % KDV line.
OTHER_ZERO_KDV_CODES: dict[str, str] = {
    "351": "KDV - İstisna Olmayan Diğer",
}

#: İhraç kayıtlı satış codes (IHRACKAYITLI invoice type).
IHRACKAYITLI_EXEMPTION_CODES: dict[str, str] = {
    "701": "3065 s. KDV Kanununun 11/1-c md. Kapsamındaki İhraç Kayıtlı Satış",
    "702": "DİİB ve Geçici Kabul Rejimi Kapsamındaki Satışlar",
    "703": "4760 s. ÖTV Kanununun 8/2 md. Kapsamındaki İhraç Kayıtlı Satış",
    "704": "3065 s. KDV Kanununun 11/1-c md. ve 4760 s. ÖTV Kanununun 8/2 md. Kapsamındaki "
    "İhraç Kayıtlı Satış",
}

#: Özel matrah codes (OZELMATRAH invoice type).
OZELMATRAH_CODES: dict[str, str] = {
    "801": "Milli Piyango, Spor Toto vb. Oyunlar",
    "802": "At Yarışları ve Diğer Müşterek Bahis ve Talih Oyunları",
    "803": "Profesyonel Sanatçıların Yer Aldığı Gösteriler, Konserler ve Sportif Faaliyetler",
    "804": "Gümrük Depolarında ve Müzayede Mahallerinde Yapılan Satışlar",
    "805": "Altından Mamul veya Altın İçeren Ziynet Eşyaları ile Sikke Altınların Teslimi",
    "806": "Tütün Mamulleri",
    "807": "Muzır Neşriyat Kapsamındaki Gazete, Dergi vb. Periyodik Yayınlar",
    "808": "Gümüşten Mamul veya Gümüş İçeren Ziynet Eşyaları ile Sikke Gümüşlerin Teslimi",
    "809": "Belediyelerin Şehir İçi Yolcu Taşımacılığı Bilet ve Kartlarının Bayilerce Satışı",
    "810": "Ön Ödemeli Elektronik Haberleşme Hizmetleri",
    "811": "TŞOF Tarafından Araç Plakaları ile Sürücü Kursu Evraklarının Teslimi",
    "812": "KDV Uygulanmadan Alınan İkinci El Motorlu Kara Taşıtı veya Taşınmaz Teslimi",
}


def exemption_reason_name(code: str) -> str | None:
    """Return GİB's name for an exemption / özel matrah code, if known."""
    for table in (
        ISTISNA_EXEMPTION_CODES,
        OTHER_ZERO_KDV_CODES,
        IHRACKAYITLI_EXEMPTION_CODES,
        OZELMATRAH_CODES,
    ):
        if code in table:
            return table[code]
    return None


#: Common UN/ECE Recommendation 20 unit codes used on Turkish invoices.
UNIT_CODES: dict[str, str] = {
    "C62": "Adet",
    "NIU": "Adet",
    "PR": "Çift",
    "SET": "Set",
    "CEN": "Yüz adet",
    "T3": "Bin adet",
    "BX": "Kutu",
    "PA": "Paket",
    "KGM": "Kilogram",
    "GRM": "Gram",
    "TNE": "Ton",
    "LTR": "Litre",
    "MTR": "Metre",
    "MTK": "Metrekare",
    "MTQ": "Metreküp",
    "SM3": "Standart metreküp",
    "KWH": "Kilovatsaat",
    "MWH": "Megavatsaat",
    "KWT": "Kilovat",
    "MIN": "Dakika",
    "HUR": "Saat",
    "DAY": "Gün",
    "MON": "Ay",
    "ANN": "Yıl",
}

#: Common UN/EDIFACT 4461 payment means codes.
PAYMENT_MEANS_CODES: dict[str, str] = {
    "1": "Belirtilmemiş",
    "10": "Nakit",
    "20": "Çek",
    "30": "Kredi transferi",
    "42": "Banka hesabına ödeme (havale / EFT)",
    "48": "Banka / kredi kartı",
    "49": "Otomatik ödeme talimatı",
    "97": "Mahsup",
    "ZZZ": "Diğer",
}

#: Currency names used for the amount-in-words note: (main unit, sub unit).
CURRENCY_NAMES: dict[str, tuple[str, str]] = {
    "TRY": ("Türk Lirası", "Kuruş"),
    "USD": ("ABD Doları", "Sent"),
    "EUR": ("Euro", "Sent"),
    "GBP": ("İngiliz Sterlini", "Peni"),
    "CHF": ("İsviçre Frangı", "Santim"),
    "JPY": ("Japon Yeni", "Sen"),
    "SAR": ("Suudi Arabistan Riyali", "Halala"),
    "AED": ("BAE Dirhemi", "Fils"),
    "RUB": ("Rus Rublesi", "Kopek"),
    "CNY": ("Çin Yuanı", "Fen"),
}
