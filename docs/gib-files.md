# GİB dosyaları ve lisans durumu / GİB files and licensing

*Son kontrol / last checked: 27 Kasım 2026.* Bu not hukuki görüş değildir. / This note is not legal advice.

## Türkçe

Doğrulama için kullanılan dosyalar Gelir İdaresi Başkanlığı'nın (GİB) kamuya açık sitesinden indirilir:

| Paket | Adres | İçerik |
|---|---|---|
| UBL-TR 1.2.1 Paketi | `https://ebelge.gib.gov.tr/dosyalar/kilavuzlar/UBL-TR1.2.1_Paketi.zip` | XSD şemaları (`xsdrt/`), örnek XML'ler, XSLT'ler |
| e-Fatura Paketi | `https://ebelge.gib.gov.tr/efaturamevzuat.html` sayfasındaki güncel `e-FaturaPaketi*.zip` bağlantısı | Schematron kuralları (`schematron/`), WSDL, zarf şemaları, örnekler |

**Lisans bulguları**

- ebelge.gib.gov.tr sayfalarının alt bilgisinde **"© Gelir İdaresi Başkanlığı Her Hakkı Saklıdır"** yazar.
- İndirilen paketlerde lisans, telif veya yeniden dağıtım izni içeren bir dosya (LICENSE, README vb.) **yoktur**.
- `xsdrt/common/*.xsd` dosyaları OASIS UBL 2.1'den türetilmiştir ve OASIS telif bildirimi ("Copyright (c) OASIS Open 2013. All Rights Reserved.") taşır; `CCTS_CCT_SchemaModule` UN/CEFACT, `xmldsig` şeması W3C bildirimi içerir. Ancak bu dosyalar GİB tarafından değiştirilmiştir (ör. `UBLExtensions` ve `cac:Signature` zorunlu hâle getirilmiştir) ve değişikliklerin hangi şartlarla paylaşıldığı belirtilmemiştir.
- Schematron dosyaları, örnek faturalar ve `general.xslt` herhangi bir lisans bildirimi içermez.

**Sonuç:** Yeniden dağıtıma açıkça izin verilmediği için GİB dosyaları bu depoya eklenmez, Python paketine gömülmez ve CI önbelleği dışında saklanmaz. `efatura schemas fetch` dosyaları kullanıcının makinesine doğrudan GİB'den indirir; önbellekteki `manifest.json` kaynağı ve sha256 özetini kaydeder. HTML önizleme GİB'in XSLT'si kullanılmadan sıfırdan yazılmıştır; GİB logosu kullanılmaz.

Kod listelerindeki kod değerleri (vergi, tevkifat, istisna kodları vb.) birlikte çalışabilirlik için gerekli olgulardır; Türkçe açıklamalar GİB'in *UBL-TR Kod Listeleri* kılavuzundan özetlenmiştir.

GİB ileride açık bir lisans yayımlarsa bu karar yeniden değerlendirilebilir.

## English

Validation files are downloaded at runtime from GİB's public website (see table above).

**Findings**

- The ebelge.gib.gov.tr footer reads **"© Gelir İdaresi Başkanlığı Her Hakkı Saklıdır"** (all rights reserved).
- The ZIP packages contain **no** license, copyright or redistribution notice of their own.
- The common XSDs derive from OASIS UBL 2.1 and keep the OASIS copyright notice (plus UN/CEFACT and W3C notices for two modules), but GİB modified them (for example `UBLExtensions` and `cac:Signature` are mandatory) without stating terms for the modified versions.
- The schematron rules, sample invoices and `general.xslt` carry no license notice at all.

**Decision:** because redistribution is not clearly permitted, GİB's files are not committed to this repository, not bundled in the Python package, and only cached on the user's machine (or in the CI cache) after downloading them directly from GİB. The HTML preview is an original template and does not use GİB's XSLT or logos.
