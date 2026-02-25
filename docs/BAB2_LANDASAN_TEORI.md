# BAB II LANDASAN TEORI

## 2.1 Tinjauan Pustaka (Literature Review)

Tinjauan pustaka digunakan untuk memetakan posisi penelitian terhadap riset sebelumnya pada tiga area utama: deteksi phishing berbasis teks, deteksi berbasis URL/reputasi domain, dan pendekatan Large Language Model (LLM) untuk klasifikasi keamanan pesan.

Secara umum, penelitian terdahulu dapat dikelompokkan menjadi:
1. Pendekatan berbasis aturan (*rule-based*), unggul pada interpretabilitas tetapi lemah pada variasi bahasa.
2. Pendekatan pembelajaran mesin klasik, membutuhkan *feature engineering* dan sensitif terhadap domain data.
3. Pendekatan *deep learning*/transformer, lebih adaptif pada konteks bahasa namun menuntut data dan komputasi lebih besar.
4. Pendekatan LLM, kuat pada pemahaman konteks, tetapi berisiko tidak konsisten bila output tidak terstruktur.

Dalam konteks grup akademik, gap utama yang sering muncul pada penelitian terdahulu adalah:
1. Minimnya pemodelan konteks sosial percakapan (dosen-mahasiswa, pengumuman kelas, administrasi kampus).
2. Tingginya *false positive* ketika pesan resmi mengandung kata berisiko (mis. “verifikasi”, “akun”, “link”).
3. Belum adanya mekanisme keputusan berlapis yang menyeimbangkan kecepatan, akurasi, dan biaya inferensi.

Berdasarkan gap tersebut, penelitian ini memposisikan kontribusi pada:
1. Pipeline deteksi berlapis: *Rule-Based Triage -> Single-Shot LLM -> Multi-Agent Debate*.
2. Mekanisme konsensus dengan *early termination* untuk efisiensi ronde debat.
3. Evaluasi komparatif lintas mode (pipeline vs mad_only), lintas varian MAD (MAD3 vs MAD5), dan lintas provider LLM.

### 2.1.1 Ringkasan Kurasi Literatur Penelitian

Berdasarkan hasil kurasi pada `docs/pustaka.md`, bagian ini menggunakan format tabel ringkas yang sama (Nama, Tahun, Judul, Metode, Kesimpulan) agar konsisten dengan dokumen pustaka.

**Tabel 2.1a. Tinjauan Pustaka Terkurasi (Phishing Teks/Chat)**

| Nama | Tahun | Judul | Metode | Kesimpulan |
|---|---|---|---|---|
| MDPI | 2026 | Phishing Email Detection Using BERT and RoBERTa ([mdpi](https://www.mdpi.com/2079-3197/14/2/46)) | Fine-tuned BERT & RoBERTa | RoBERTa menekan *false negative* lebih baik, tetapi fokus utama masih email. |
| IEEE | 2020 | From Feature Engineering and Topics Models to Enhanced Prediction Rates in Phishing Detection ([ieeexplore.ieee](https://ieeexplore.ieee.org/document/9075252/)) | Feature engineering + LDA + XGBoost | Kinerja sangat tinggi pada domain tertentu, namun ketergantungan fitur manual masih kuat. |
| arXiv | 2024 | An Explainable Transformer-based Model for Phishing Email Detection ([arxiv](https://arxiv.org/pdf/2402.13871.pdf)) | DistilBERT + LIME | Explainability membantu audit keputusan, tetapi biaya komputasi meningkat. |
| ACM | 2021 | Hybrid CNN-GRU Framework with Integrated Pre-trained Language Transformer for SMS Phishing Detection ([dl.acm](https://dl.acm.org/doi/10.1145/3508072.3508109)) | MPNet + CNN + Bi-GRU | Pendekatan hybrid efektif untuk SMS, namun arsitektur lebih kompleks untuk dipelihara. |

**Tabel 2.1b. Tinjauan Pustaka Terkurasi (URL/Domain)**

| Nama | Tahun | Judul | Metode | Kesimpulan |
|---|---|---|---|---|
| IEEE | 2020 | Texception: A Character/Word-Level Deep Learning Model for Phishing URL Detection ([ieeexplore.ieee](https://ieeexplore.ieee.org/document/9053670/)) | Parallel conv layers (char + word) | URL-only deep model kuat untuk skala besar, namun belum memakai konteks pesan. |
| ACM | 2020 | Visualizing and Interpreting RNN Models in URL-based Phishing Detection ([dl.acm](https://dl.acm.org/doi/10.1145/3381991.3395602)) | Ensemble RNN + lexical features | Akurasi tinggi dan interpretasi visual membantu analisis, tetapi kompleksitas model meningkat. |
| IEEE | 2020 | PhishHaven—An Efficient Real-Time AI Phishing URLs Detection System ([ieeexplore.ieee](https://ieeexplore.ieee.org/document/9082616/)) | Ensemble + voting + lexical features | Penanganan *tiny URL* baik, namun voting statis belum adaptif pada kasus ambigu. |
| Nature | 2026 | Metadata driven malicious URL detection using RoBERTa large ([nature](https://www.nature.com/articles/s41598-025-34790-x)) | RoBERTa-Large + metadata + SHAP/LIME | Kombinasi teks dan metadata efektif, tetapi kebutuhan resource relatif berat. |

**Tabel 2.1c. Tinjauan Pustaka Terkurasi (LLM Security)**

| Nama | Tahun | Judul | Metode | Kesimpulan |
|---|---|---|---|---|
| arXiv | 2025 | SpaLLM-Guard: Pairing SMS Spam Detection Using Open-source and Commercial LLMs ([arxiv](https://arxiv.org/pdf/2501.04985.pdf)) | Fine-tuned LLM + few-shot | LLM adaptif terhadap *concept drift*, namun biaya tuning dan inferensi tetap perlu dikontrol. |
| IEEE | 2025 | A Hybrid NLP and Deep Learning Framework for Intelligent SMS Phishing Detection ([ieeexplore.ieee](https://ieeexplore.ieee.org/document/11346167/)) | Hybrid LSTM + URL features + RF | Integrasi sinyal teks dan URL meningkatkan deteksi *smishing*. |
| Wiley | 2024 | Enhancing Phishing Detection: A Machine Learning Approach ([onlinelibrary.wiley](https://onlinelibrary.wiley.com/doi/10.1155/acis/6633979)) | Multi-model ensemble | Ensemble memberi akurasi tinggi, tetapi overhead operasional cukup besar. |

**Tabel 2.1d. Tinjauan Pustaka Terkurasi (Multi-Agent Debate)**

| Nama | Tahun | Judul | Metode | Kesimpulan |
|---|---|---|---|---|
| arXiv | 2024 | Encouraging Divergent Thinking in Large Language Models through Multi-Agent Debate ([arxiv](http://arxiv.org/pdf/2305.19118.pdf)) | MAD framework + judge | Menjadi fondasi teori debat multi-agen untuk meningkatkan kualitas penalaran. |
| arXiv | 2025 | MALLM: Multi-Agent Large Language Models Framework ([arxiv](https://arxiv.org/abs/2509.11656)) | 144+ konfigurasi MAD | Menyediakan kerangka sistematis konfigurasi MAD, tetapi kompleks untuk implementasi praktis. |
| arXiv | 2025 | Free-MAD: Consensus-Free Multi-Agent Debate ([arxiv](https://arxiv.org/abs/2509.11035)) | Score-based + anti-conformity + single-round | Menunjukkan efisiensi token melalui mekanisme mirip *early termination*. |
| arXiv | 2024 | ReConcile: Round-Table Conference Improves Reasoning via Consensus among Diverse LLMs ([arxiv](http://arxiv.org/pdf/2309.13007.pdf)) | Confidence-weighted consensus | Voting berbobot meningkatkan kolaborasi agen, relevan untuk agregasi keputusan MAD. |
| ACL Findings | 2025 | CONSENSAGENT ([aclanthology](https://aclanthology.org/2025.findings-acl.1141)) | Dynamic prompt refinement | Mitigasi *sycophancy* meningkatkan stabilitas konsensus pada interaksi multi-agen. |

**Ringkasan Kurasi**

Total referensi inti pada Tabel 2.1 (a-d): **16 paper**. Komposisi ini dipilih agar fokus pada gap yang paling relevan untuk TelePhisDebate: integrasi analisis teks + URL, output LLM terstruktur, dan keputusan kolektif berbasis MAD.

> **Placeholder Gambar 2.1**  
> Peta *state of the art* dan posisi penelitian saat ini.

> **Catatan Sitasi APA**  
> Metadata bibliografi (penulis, tahun, venue, DOI/URL) pada tabel terkurasi ini tetap perlu verifikasi akhir sebelum disalin ke daftar pustaka skripsi.

## 2.2 Dasar Teori

### 2.2.1 Phishing dan Rekayasa Sosial

Phishing merupakan serangan yang memanfaatkan manipulasi psikologis agar korban menyerahkan informasi sensitif atau melakukan aksi berisiko. Pada media chat, serangan sering disamarkan sebagai pesan resmi agar menurunkan kewaspadaan.

Elemen rekayasa sosial yang umum:
1. **Urgency/pressure**: memaksa korban bertindak cepat.
2. **Authority impersonation**: mengatasnamakan admin, dosen, atau institusi.
3. **Reward/fear trigger**: iming-iming hadiah atau ancaman pemblokiran akun.

Dalam grup akademik, elemen tersebut sering dibungkus dengan konteks perkuliahan sehingga perlu analisis yang memperhatikan isi pesan sekaligus konteks.

### 2.2.2 Pemrosesan Teks untuk Deteksi Ancaman

Pemrosesan teks pada sistem deteksi pesan berbahaya umumnya mencakup:
1. *Cleaning* (normalisasi noise, tanda baca, format URL).
2. *Normalization* (lowercase, penyeragaman pola kata informal).
3. Ekstraksi indikator linguistik (kata kunci risiko, pola ajakan tindakan, penyalahgunaan huruf kapital).

Prinsip teoritisnya adalah mengubah teks mentah menjadi representasi yang lebih stabil agar keputusan model lebih konsisten.

### 2.2.3 Analisis URL dan Reputasi Domain

URL merupakan indikator penting karena banyak serangan phishing bergantung pada tautan.

Komponen teoretis analisis URL:
1. **URL expansion**: membuka shortener (bit.ly, s.id, dst.) ke URL tujuan akhir.
2. **Heuristic URL risk**: menilai TLD, pola domain, HTTPS, path/query berisiko.
3. **External reputation**: memanfaatkan sumber eksternal (mis. VirusTotal) sebagai bukti objektif.

Pendekatan gabungan ini mengurangi ketergantungan pada isi teks semata.

> **Placeholder Gambar 2.2**  
> Ilustrasi alur social engineering phishing pada media chat.

> **Placeholder Gambar 2.3**  
> Diagram proses preprocessing teks dan analisis URL.

### 2.2.4 Rule-Based Triage

*Rule-based triage* adalah tahap penyaringan awal berbasis aturan deterministik. Tujuan utamanya:
1. Menyelesaikan kasus jelas dengan cepat.
2. Mengurangi beban panggilan LLM.
3. Menjaga interpretabilitas keputusan awal.

Secara umum, *triage* menghasilkan:
1. Klasifikasi awal risiko.
2. Daftar *triggered flags*.
3. Skor risiko agregat untuk memandu eskalasi tahap berikutnya.

### 2.2.5 Single-Shot LLM

Single-shot LLM berfungsi sebagai pengambil keputusan menengah untuk kasus non-trivial. Secara teori, LLM unggul dalam:
1. Memahami konteks semantik.
2. Menangkap pola bahasa manipulatif yang tidak eksplisit.
3. Menghasilkan alasan keputusan.

Namun, agar reliabel di sistem produksi, output LLM harus dipaksa terstruktur (JSON schema) dan diparsing secara robust.

### 2.2.6 Multi-Agent Debate (MAD)

MAD adalah pendekatan pengambilan keputusan kolektif, di mana beberapa agen berperan dengan perspektif berbeda.

Konsep dasarnya:
1. Tiap agen menghasilkan *stance* dan *confidence*.
2. Agen dapat berdeliberasi lintas ronde.
3. Keputusan akhir diperoleh melalui agregasi berbobot.

Pada penelitian ini:
1. **MAD3**: lebih ringan dan efisien.
2. **MAD5**: lebih kaya peran (detector, critic, defender, fact-checker, judge) dan diharapkan lebih stabil pada kasus ambigu.

### 2.2.7 Konsensus, Voting, dan Early Termination

Secara teoretis, konsensus digunakan untuk menghentikan proses deliberasi saat keputusan sudah cukup stabil.

Misal skor teragregasi didefinisikan sebagai:

\[
S = \frac{\sum_{i=1}^{n} w_i \cdot c_i \cdot v_i}{\sum_{i=1}^{n} w_i}
\]

dengan:
1. \(w_i\): bobot agen ke-\(i\),
2. \(c_i\): confidence agen ke-\(i\),
3. \(v_i\): nilai sikap agen ke-\(i\) (mis. pemetaan stance ke skala keputusan).

Jika kondisi konsensus terpenuhi, proses dihentikan (*early termination*). Jika tidak, proses berlanjut hingga maksimum ronde.

> **Placeholder Gambar 2.4**  
> Diagram mekanisme deliberasi multi-round dan early termination.

### 2.2.8 Metrik Evaluasi Klasifikasi

Evaluasi kinerja klasifikasi didasarkan pada confusion matrix:
1. TP (True Positive),
2. FP (False Positive),
3. FN (False Negative),
4. TN (True Negative).

Metrik utama:

\[
Accuracy = \frac{TP + TN}{TP + FP + FN + TN}
\]

\[
Precision = \frac{TP}{TP + FP}
\]

\[
Recall = \frac{TP}{TP + FN}
\]

\[
F1 = 2 \cdot \frac{Precision \cdot Recall}{Precision + Recall}
\]

Detection Rate (sesuai definisi penelitian) digunakan untuk melihat kemampuan sistem menangkap kasus ancaman:

\[
Detection\ Rate = \frac{\text{PHISHING atau SUSPICIOUS yang terdeteksi}}{\text{total PHISHING aktual}}
\]

Selain metrik klasifikasi, dipakai pula metrik operasional:
1. Rata-rata waktu proses per pesan.
2. Konsumsi token per pesan.
3. Distribusi kontribusi tiap stage.

> **Placeholder Gambar 2.5**  
> Contoh confusion matrix dan grafik perbandingan metrik.

## 2.3 Kerangka Pemikiran

Kerangka pemikiran menjelaskan alur logis pemecahan masalah penelitian.

1. **Permasalahan**: grup akademik rentan menerima pesan phishing yang menyerupai pesan resmi.
2. **Keterbatasan pendekatan tunggal**: rule-only kurang adaptif, model-only berisiko tidak stabil dan mahal.
3. **Pendekatan usulan**: pipeline berlapis untuk menyeimbangkan efisiensi dan ketelitian.
4. **Mekanisme peningkatan kualitas**: eskalasi kasus ambigu ke MAD, lalu konsensus berbasis voting.
5. **Validasi empiris**: pengujian komparatif MAD3/MAD5, pipeline/mad_only, serta provider model.

Secara sistematis, objek penelitian adalah pesan grup Telegram akademik (teks/caption dan URL terkait) yang diproses menjadi keputusan SAFE, SUSPICIOUS, atau PHISHING.

> **Placeholder Gambar 2.6**  
> Diagram kerangka pemikiran penelitian (problem -> method -> evaluation -> conclusion).

### 2.3.1 Notasi Flowchart yang Digunakan

Tabel berikut menjelaskan notasi flowchart yang digunakan pada diagram sistem penelitian ini.

| No | Nama Notasi | Fungsi | Bentuk Umum | Notasi Mermaid yang Dipakai | Contoh pada Diagram |
|---|---|---|---|---|---|
| 1 | Terminator | Menandai awal/akhir alur proses | Oval / rounded | `([Start])`, `([End])` | Mulai proses deteksi, akhir proses logging |
| 2 | Input/Output | Menunjukkan data masuk atau keluaran proses | Paralelogram | `[/Input .../]`, `[/Output .../]` | Input pesan Telegram, output keputusan akhir |
| 3 | Process | Menunjukkan aktivitas atau langkah kerja | Persegi panjang | `[Process: ...]` | Rule-Based Triage, Single-Shot LLM, Multi-Agent Debate |
| 4 | Decision | Menunjukkan percabangan berdasarkan kondisi | Belah ketupat | `{Decision: ...}` | "Perlu Eskalasi?", "Ambigu/Risiko Tinggi?" |
| 5 | Flowline | Menunjukkan arah aliran proses | Garis panah | `-->` | Alur dari input menuju keputusan dan output |

> **Placeholder Gambar 2.7**  
> Flowchart detail alur sistem TelePhisDebate.

## 2.4 Hipotesis (Jika Ada)

Hipotesis disusun dari kerangka pemikiran untuk diuji secara empiris.

Hipotesis penelitian (H1):
1. **H1-1**: Pipeline berlapis meningkatkan kualitas deteksi dibanding pendekatan single-stage.
2. **H1-2**: Penggunaan MAD pada kasus ambigu meningkatkan keseimbangan precision-recall.
3. **H1-3**: Terdapat perbedaan kinerja antara MAD3 dan MAD5 pada akurasi, waktu, dan konsumsi token.

Hipotesis nol (H0):
1. **H0-1**: Tidak ada perbedaan signifikan kualitas deteksi antara pipeline berlapis dan single-stage.
2. **H0-2**: Penggunaan MAD tidak meningkatkan kualitas keputusan secara signifikan.
3. **H0-3**: Tidak ada perbedaan signifikan antara MAD3 dan MAD5 pada metrik evaluasi.

Variabel yang dapat diuji:
1. Variabel bebas: mode evaluasi, varian MAD, provider/model LLM.
2. Variabel terikat: accuracy, precision, recall, F1-score, detection rate, waktu proses, token.

> **Placeholder Tabel 2.2**  
> Tabel operasional hipotesis (H1/H0, variabel, indikator, metode uji).

## 2.5 Ringkasan Bab

Bab ini menegaskan bahwa deteksi phishing pada komunikasi akademik membutuhkan pendekatan multi-komponen: analisis teks, analisis URL, klasifikasi bertahap, dan mekanisme debat multi-agen. Kerangka teori tersebut menjadi dasar perancangan metode pada bab berikutnya.
