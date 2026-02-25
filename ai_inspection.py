import cv2
import time
import snap7
from snap7.util import set_int
import logging

# --- KONFIGÜRASYON ---
# PLCSIM IP Adresi (NetToPLCSim kullanıyorsan PC IP'si olabilir, yoksa PLC IP'si)
PLC_IP = "192.168.10.200" # Fiziksel PLC IP'si (Kendi PLC IP'niz ile değiştirin) 
RACK = 0
SLOT = 1 # S7-1200/1500 için genelde 1'dir. S7-300 için 2 olabilir.

# Hangi DB'ye ve Hangi Byte'a yazacağız?
# TIA Portal'da DB_AI_Communication bloğunun numarası (Properties -> General -> Number)
DB_NUMBER = 1 
# Offsetler: SCL dosyasında ilk Int (AI_Result) 0. byte, ikinci Int (Defect) 2. byte başlar.
OFFSET_RESULT = 0
OFFSET_DEFECT = 2

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PolteksAI")

def main():
    print(f"--- Polteks AI Surface Inspection (Snap7) ---")
    print(f"PLC Bağlanıyor: {PLC_IP} Rack:{RACK} Slot:{SLOT}")
    
    client = snap7.client.Client()
    try:
        client.connect(PLC_IP, RACK, SLOT)
        logger.info(f"PLC Bağlantısı Başarılı! ({PLC_IP})")
        
        # --- DOGRULAMA ICIN OKUMA TESTI ---
        try:
            # 4 Byte oku (Result + Defect Int değerleri)
            test_read = client.db_read(DB_NUMBER, 0, 4)
            logger.info(f"OKUMA TESTİ VE BAĞLANTI İYİ: Mevcut DB Verisi: {list(test_read)}")
        except Exception as read_err:
            logger.error(f"OKUMA HATASI! Put/Get izni veya DB Numarası hatalı olabilir: {read_err}")
    except Exception as e:
        logger.error(f"PLC Bağlantı Hatası: {e}")
        logger.warning("Simülasyon Modu: PLC'ye yazılmayacak, sadece ekranda görünecek.")
        client = None

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.error("Webcam açılamadı!")
        return

    print("Sistem Hazır. 'q' tuşu ile çıkış yapabilirsiniz.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        # Görüntü İşleme (Kırmızı Tespiti)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Kırmızı Renk Maskesi
        lower_red1 = (0, 100, 100); upper_red1 = (10, 255, 255)
        lower_red2 = (170, 100, 100); upper_red2 = (180, 255, 255)
        mask = cv2.inRange(hsv, lower_red1, upper_red1) + cv2.inRange(hsv, lower_red2, upper_red2)
        
        red_pixels = cv2.countNonZero(mask)
        
        # --- KARAR MEKANİZMASI ---
        # 1: OK, 2: HATA (NOK)
        current_result = 1 
        current_defect = 0
        
        if red_pixels > 500: # Eşik Değer
            current_result = 2 # HATA
            current_defect = 1 # Tip: Leke
            
            # Görselleştirme
            cv2.putText(frame, "HATA: YUZEY KUSURU", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cv2.rectangle(frame, (10, 10), (frame.shape[1]-10, frame.shape[0]-10), (0, 0, 255), 10)
        else:
            current_result = 1 # SAGLAM
            cv2.putText(frame, "URUN SAGLAM", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.rectangle(frame, (10, 10), (frame.shape[1]-10, frame.shape[0]-10), (0, 255, 0), 5)

        # --- PLC YAZMA ---
        if client and client.get_connected():
            try:
                # 4 Byte'lık bir buffer oluştur (2 Int yazacağız)
                data = bytearray(4)
                set_int(data, OFFSET_RESULT, current_result)
                set_int(data, OFFSET_DEFECT, current_defect)
                
                # DB'ye yaz (DB Read/Write fonksiyonu)
                client.db_write(DB_NUMBER, 0, data)
                print(f"PLC'ye Yazıldı -> Sonuç: {current_result} (1:OK, 2:HATA), Tip: {current_defect}")
                
            except Exception as e:
                logger.error(f"PLC Yazma Hatası: {e}")
        
        cv2.imshow('Polteks AI Inspection', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    if client:
        client.disconnect()

if __name__ == "__main__":
    main()
