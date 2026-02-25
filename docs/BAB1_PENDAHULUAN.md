# BAB I PENDAHULUAN

## 1.1 Latar Belakang

Perkembangan teknologi komunikasi digital telah mengubah pola interaksi di lingkungan akademik. Grup Telegram menjadi media utama untuk penyampaian informasi perkuliahan, jadwal ujian, pengumuman administratif, hingga koordinasi tugas. Kemudahan ini meningkatkan kecepatan komunikasi, tetapi juga membuka celah terhadap penyebaran pesan berbahaya seperti phishing.

**Fakta:** Serangan phishing terus berkembang dengan memanfaatkan rekayasa sosial, tautan palsu, dan impersonasi pihak resmi. Dalam konteks grup akademik, pelaku dapat menyamarkan pesan seolah-olah berasal dari dosen, admin, atau unit kampus. Pola ini berisiko menipu mahasiswa agar memberikan data sensitif, melakukan transfer, atau mengakses tautan tidak aman.

**Masalah:** Moderasi manual di grup Telegram memiliki keterbatasan. Volume pesan yang tinggi, variasi bahasa informal, dan kemiripan antara pesan valid dan pesan penipuan membuat deteksi cepat menjadi sulit. Pendekatan berbasis aturan saja sering gagal menangani kasus ambigu, sedangkan klasifikasi satu model tunggal berpotensi menghasilkan false positive atau false negative yang berdampak pada kepercayaan pengguna.

**Solusi:** Penelitian ini mengusulkan sistem deteksi phishing berbasis *Multi-Agent Debate* (MAD) pada Telegram, yang dipadukan dengan pipeline bertahap: *rule-based triage*, *single-shot LLM*, dan analisis debat multi-agen untuk kasus ambigu. Pendekatan ini dirancang agar tetap efisien pada pesan normal, namun lebih teliti pada pesan berisiko tinggi. Sistem juga menyediakan evaluasi komparatif mode MAD3 dan MAD5 untuk menilai keseimbangan akurasi, kecepatan, serta ketahanan keputusan.

Berdasarkan kondisi tersebut, pengembangan TelePhisDebate menjadi relevan sebagai upaya meningkatkan keamanan komunikasi digital akademik secara adaptif, terukur, dan dapat diintegrasikan langsung pada alur komunikasi grup.

## 1.2 Identifikasi Masalah

Berdasarkan latar belakang, masalah yang dapat diidentifikasi adalah sebagai berikut:

1. Tingginya potensi penyebaran pesan phishing pada grup Telegram akademik.
2. Sulitnya membedakan pesan resmi dan pesan manipulatif karena pola bahasa yang mirip.
3. Keterbatasan moderasi manual dalam merespons ancaman secara cepat dan konsisten.
4. Pendekatan deteksi tunggal cenderung tidak stabil pada kasus ambigu.
5. Belum optimalnya mekanisme verifikasi berlapis yang menyeimbangkan akurasi dan efisiensi proses.

## 1.3 Rumusan Masalah

Rumusan masalah dalam penelitian ini adalah:

1. Bagaimana merancang sistem deteksi phishing berbasis Telegram yang mampu bekerja pada konteks komunikasi akademik?
2. Bagaimana menerapkan pendekatan *Multi-Agent Debate* untuk meningkatkan kualitas keputusan pada pesan ambigu?
3. Bagaimana kinerja sistem pada mode MAD3 dan MAD5 ditinjau dari akurasi, F1-score, detection rate, dan waktu proses?

## 1.4 Batasan Masalah

Batasan masalah pada penelitian ini meliputi:

1. Objek penelitian difokuskan pada pesan teks/caption dalam grup Telegram akademik.
2. Klasifikasi keluaran dibatasi pada kategori SAFE, SUSPICIOUS, dan PHISHING.
3. Analisis berfokus pada deteksi konten phishing berbasis teks dan tautan, bukan analisis gambar/audio.
4. Pengujian dilakukan menggunakan dataset evaluasi yang disiapkan untuk konteks akademik dan perbandingan mode MAD3 serta MAD5.
5. Implementasi sistem menggunakan arsitektur pipeline TelePhisDebate sesuai ruang lingkup proyek skripsi.

## 1.5 Manfaat Penelitian

Manfaat penelitian ini adalah:

1. **Bagi akademik:** Menyediakan referensi implementasi deteksi phishing berbasis *multi-agent* pada lingkungan komunikasi pendidikan.
2. **Bagi institusi:** Membantu meningkatkan keamanan informasi di grup komunikasi kampus melalui deteksi dini pesan berisiko.
3. **Bagi pengguna (mahasiswa/dosen):** Mengurangi potensi kerugian akibat penipuan digital melalui peringatan dan klasifikasi otomatis.
4. **Bagi pengembangan sistem:** Menjadi dasar pengembangan lanjutan untuk integrasi kebijakan moderasi cerdas yang lebih adaptif.

