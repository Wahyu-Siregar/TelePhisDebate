# BAB I PENDAHULUAN

## 1.1 Latar Belakang

Perkembangan teknologi komunikasi digital telah mengubah pola interaksi di lingkungan akademik. Grup Telegram menjadi media utama untuk penyampaian informasi perkuliahan, jadwal ujian, pengumuman administratif, hingga koordinasi tugas. Kemudahan ini meningkatkan kecepatan komunikasi, tetapi juga membuka celah terhadap penyebaran pesan berbahaya seperti phishing.

Serangan phishing terus berkembang dengan memanfaatkan rekayasa sosial, tautan palsu, dan impersonasi pihak resmi. Dalam konteks grup akademik, pelaku dapat menyamarkan pesan seolah-olah berasal dari dosen, admin, atau unit kampus — pola ini berisiko menipu mahasiswa agar memberikan data sensitif, melakukan transfer, atau mengakses tautan berbahaya (Kytidou et al., 2025). Platform pesan instan seperti Telegram menjadi medium yang rentan karena pengguna cenderung meneruskan dan mengklik tautan dari kontak yang dikenal tanpa verifikasi terlebih dahulu (Verma et al., 2023).

Moderasi manual di grup Telegram menghadapi keterbatasan yang nyata: volume pesan yang tinggi, variasi bahasa informal, dan kemiripan antara pesan valid dengan pesan penipuan menyulitkan deteksi yang cepat dan konsisten. Pendekatan berbasis aturan (*rule-based*) saja kerap gagal menangani kasus ambigu, sementara klasifikasi dengan satu model tunggal berpotensi menghasilkan *false positive* atau *false negative* yang merugikan kepercayaan pengguna (Trad & Chehab, 2025).

Penelitian ini mengusulkan sistem deteksi phishing berlapis berbasis *Multi-Agent Debate* (MAD) pada grup Telegram akademik, yang menggabungkan *rule-based triage*, *single-shot LLM*, dan analisis debat multi-agen untuk kasus ambigu. Pendekatan MAD terbukti meningkatkan kalibrasi dan ketahanan keputusan dibanding inferensi agen tunggal melalui mekanisme deliberasi lintas-agen (Nguyen et al., 2025; Sachdeva & van Nuenen, 2025). Sistem juga menyediakan evaluasi komparatif mode MAD3 dan MAD5 untuk menilai keseimbangan akurasi, kecepatan, serta ketahanan keputusan.

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
3. Bagaimana kinerja sistem pada mode MAD3 dan MAD5 ditinjau dari akurasi, F1-score, detection rate, waktu proses, dan efisiensi konsumsi token?

## 1.4 Batasan Masalah

Batasan masalah pada penelitian ini meliputi:

1. Objek penelitian difokuskan pada pesan teks/caption dalam grup Telegram akademik.
2. Klasifikasi keluaran dibatasi pada kategori SAFE, SUSPICIOUS, dan PHISHING.
3. Analisis berfokus pada deteksi konten phishing berbasis teks dan tautan, bukan analisis gambar/audio.
4. Pengujian dilakukan menggunakan dataset evaluasi yang disiapkan untuk konteks akademik, mencakup perbandingan mode MAD3 dan MAD5, serta perbandingan provider LLM (DeepSeek dan OpenRouter).
5. Implementasi sistem menggunakan arsitektur pipeline TelePhisDebate sesuai ruang lingkup proyek skripsi.

## 1.5 Manfaat Penelitian

Manfaat penelitian ini adalah:

1. **Bagi akademik:** Menyediakan referensi implementasi deteksi phishing berbasis *multi-agent* pada lingkungan komunikasi pendidikan.
2. **Bagi institusi:** Membantu meningkatkan keamanan informasi di grup komunikasi kampus melalui deteksi dini pesan berisiko.
3. **Bagi pengguna (mahasiswa/dosen):** Mengurangi potensi kerugian akibat penipuan digital melalui peringatan dan klasifikasi otomatis.
4. **Bagi pengembangan sistem:** Menjadi dasar pengembangan lanjutan untuk integrasi kebijakan moderasi cerdas yang lebih adaptif.

---

**Referensi bagian ini:**

- Kytidou, E., Tsikriki, T., & Drosatos, G. (2025). Machine learning techniques for phishing detection: A review of methods, challenges, and future directions. *Intelligent Decision Technologies*, 19(6), 4356–4379. https://doi.org/10.1177/18724981251366763
- Nguyen, N. T. V., Childress, F. D., & Yin, Y. (2025). Debate-driven multi-agent LLMs for phishing email detection. *arXiv*. https://doi.org/10.48550/arxiv.2503.22038
- Sachdeva, P. S., & van Nuenen, T. (2025). Deliberative dynamics and value alignment in LLM debates. *arXiv*. https://doi.org/10.48550/arxiv.2510.10002
- Trad, F., & Chehab, A. (2025). CLASP: Cost-optimized LLM-based agentic system for phishing detection. *arXiv*. https://doi.org/10.48550/arxiv.2510.18585
- Verma, S., Ayala-Rivera, V., & Portillo-Dominguez, A. O. (2023). Detection of phishing in mobile instant messaging using natural language processing and machine learning. *Proceedings of IEEE CONISOFT 2023*, 159–168. https://doi.org/10.1109/conisoft58849.2023.00029

