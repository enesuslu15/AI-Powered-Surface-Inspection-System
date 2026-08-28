# Polteks AI Yüzey ve Dikiş Kontrol Sistemi - Donanım & PLC Kurulum Kılavuzu

Bu kılavuz, **Fiziksel Siemens S7-1200 / S7-1500 PLC** ile **Python AI** yazılımını nasıl entegre edip çalıştıracağınızı adım adım anlatır.

---

## 1. Donanım ve Ağ Bağlantısı

1. **Ethernet Kablosu:** Bilgisayarınızın Ethernet portu ile Siemens PLC'nin PROFINET (Ethernet) portunu bağlayın.
2. **Bilgisayar Statik IP Ayarı:**
   - Denetim Masası -> Ağ ve Paylaşım Merkezi -> Bağdaştırıcı ayarlarını değiştirin.
   - Ethernet kartınıza sağ tıklayın -> **Özellikler** -> **Internet Protokolü Sürüm 4 (TCP/IPv4)**.
   - **IP Adresi:** `192.168.1.100` (PLC ile aynı alt ağda olmalı, örn: PLC `192.168.1.20` ise `192.168.1.x` olmalıdır).
   - **Alt Ağ Maskesi:** `255.255.255.0`
   - **Varsayılan Ağ Geçidi:** Boş bırakılabilir.

---

## 2. TIA Portal Yapılandırması (Kritik Adımlar)

Siemens PLC'lerin Snap7 gibi harici üçüncü parti kütüphanelerle haberleşebilmesi için TIA Portal'da şu 3 ayarın yapılması zorunludur:

### Adım A: PUT/GET Haberleşme İzni (Güvenlik)
1. TIA Portal'da **Device configuration** ekranına gelin.
2. PLC CPU'suna tıklayın ve alt panelden **Properties -> Protection & Security -> Connection mechanisms** bölümüne gidin.
3. ☑️ **"Permit access with PUT/GET communication from remote partner"** seçeneğini **İŞARETLEYİN**.

### Adım B: Optimized Block Access Ayarı
1. Projenizdeki `plc/plc_surface_logic.scl` (veya stitching için `plc/plc_stitching_logic.scl`) dosyasını TIA Portal'a **External Source** olarak ekleyip derleyin.
2. Oluşan **`DB_AI_Communication`** (DB1) bloğuna sağ tıklayın -> **Properties** -> **Attributes**.
3. ❌ **"Optimized block access"** kutucuğunun işaretini **KALDIRIN (Boş olsun)**.
   > *Not: Bu ayarı değiştirdikten sonra DB bloğunu mutlaka tekrar derlemeniz (Compile) gerekir.*
4. DB numarasının **1** olduğundan emin olun (DB1).

### Adım C: SCL Mantığının OB1 İçinde Çağrılması
1. **Main [OB1]** bloğunu açın.
2. Bir Network içine `FB_Machine_Control` bloğunu sürükleyin (Örn: `Inst_FB_Machine_Control` adıyla Instance DB oluşur).
3. Giriş ve Çıkış pinlerini PLC I/O adreslerinize bağlayın:
   - `System_Enable_Switch` -> `%I0.1` (Sistem Anahtarı)
   - `Restart_Button` -> `%I0.0` (Restart Butonu)
   - `Motor_Cikis` -> `%Q0.0` (Motor Kontaktörü)
   - `Red_Light` -> `%Q0.1` (Kırmızı Arıza Lambası)
   - `Green_Light` -> `%Q0.2` (Yeşil Çalışıyor Lambası)

4. Projeyi PLC'ye yükleyin (**Download to device** -> Hardware + Software changes).
5. PLC'yi **RUN** moduna alın.

---

## 3. Python AI Sistemini Çalıştırma

### Bağımlılıkların Kurulumu:
```bash
pip install -r requirements.txt
```

### Yüzey Kusuru Denetimini Başlatma (MVTec AD Modeli):
```bash
# Canlı Kamera ve PLC ile:
python src/ai_inspection.py --ip 192.168.1.20 --conf 0.30

# PLC Olmadan (Simülasyon / Test Modu):
python src/ai_inspection.py --mock-plc
```

### Kumaş Dikiş Denetimini Başlatma (Deneysel 5-Sınıflı Modül):
```bash
python src/ai_stitching_inspection.py --ip 192.168.1.20
```

---

## 4. Klavye Kontrolleri ve Test

| Tuş | Fonksiyon | Açıklama |
|-----|-----------|----------|
| `[Q]` | Çıkış | Programı ve kamera akışını güvenli şekilde sonlandırır. |
| `[R]` | Motor Restart | Hata kilidi aktifken motoru yeniden başlatmak için PLC'ye sinyal gönderir. |
| `[S]` | Simülasyon Hatası | Kameranın önünde fiziksel kusur yokken test amaçlı yapay arıza tetikler. |

---

## 5. Sık Karşılaşılan Sorunlar (Troubleshooting)

* **Hata: `PLC Bağlantı Hatası: b' ISO : An error occurred during recv TCP : Connection reset by peer'`**
  * Bilgisayarınızın Ethernet IP ayarını kontrol edin (`192.168.1.100`).
  * CMD üzerinden `ping 192.168.1.20` atarak PLC'ye erişebildiğinizi doğrulayın.
  * TIA Portal'da **PUT/GET izninin** işaretli olduğundan ve donanım konfigürasyonunun PLC'ye yüklendiğinden emin olun.
* **Hata: `DB Read/Write Hatası: b' CLI : function refused by CPU'`**
  * `DB_AI_Communication` bloğunun **"Optimized Block Access"** özelliğinin kapalı (standart erişim) olduğunu doğrulayın.
  * DB numarasının Python kodundaki `--db 1` parametresiyle eşleştiğini kontrol edin.

