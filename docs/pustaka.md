Baik Wahyu, saya susun ulang dalam format tabel yang lebih sederhana:

## Tabel Tinjauan Pustaka TelePhisDebate

### Tema 1: Phishing Detection (Teks/Chat/Message)

| Nama | Tahun | Judul | Metode | Kesimpulan |
|---|---|---|---|---|
| MDPI | 2026 | Phishing Email Detection Using BERT and RoBERTa | Fine-tuned BERT & RoBERTa untuk binary classification | RoBERTa menghasilkan fewer false negatives dan better generalization, efektif untuk text-based phishing detection namun perlu ekstend ke messaging platforms  [mdpi](https://www.mdpi.com/2079-3197/14/2/46) |
| IAES Prime | 2020 | Email Phishing: Text Classification Using Natural Language Processing | NLP preprocessing + multiple classifiers | NLP concepts dengan multiple classifiers efektif untuk phishing email, namun manual feature engineering membatasi adaptability sistem  [iaesprime](http://iaesprime.com/index.php/csit/article/view/8) |
| IEEE | 2020 | From Feature Engineering and Topics Models to Enhanced Prediction Rates in Phishing Detection | Feature engineering + LDA + XGBoost | XGBoost mencapai F1-measure 99.95% dengan kombinasi feature engineering dan topic modeling, namun hanya menggunakan body email tanpa metadata  [ieeexplore.ieee](https://ieeexplore.ieee.org/document/9075252/) |
| Hindawi | 2022 | A Deep Learning Filter that Blocks Phishing Campaigns Using Intelligent English Text Recognition Methods | LSTM + CNN untuk hidden information extraction | LSTM-CNN berhasil capture hidden information untuk block phishing campaigns, namun terbatas pada dataset dengan labeling scheme terbatas  [downloads.hindawi](https://downloads.hindawi.com/journals/abb/2022/5036026.pdf) |
| arXiv | 2024 | An Explainable Transformer-based Model for Phishing Email Detection: A Large Language Model Approach | Optimized DistilBERT + LIME + Transformer Interpret | DistilBERT dengan LIME menghasilkan high accuracy dan explainability, membuktikan pentingnya interpretable AI untuk phishing detection  [arxiv](https://arxiv.org/pdf/2402.13871.pdf) |
| arXiv | 2019 | Catching the Phish: Detecting Phishing Attacks using Recurrent Neural Networks (RNNs) | RNN-based classifier untuk textual structure | RNN outperforms state-of-the-art tools dengan efficient processing untuk textual structure, namun tidak capture semantic meaning  [arxiv](https://arxiv.org/pdf/1908.03640.pdf) |
| Semantic Scholar | 2020 | Text Data Augmentation: Towards better detection of spear-phishing emails | BERT + multi-step back-translation + heuristics | Data augmentation dengan BERT dan back-translation meningkatkan performance text classification untuk spear-phishing detection  [semanticscholar](https://www.semanticscholar.org/paper/885275636fcde952a41f5272af72bc956b106f3d) |
| arXiv | 2022 | Federated Phish Bowl: LSTM-Based Decentralized Phishing Email Detection | Federated learning + LSTM + NLP | Federated learning approach memungkinkan privacy-preserving phishing detection secara decentralized, mirip konsep multi-agent namun tanpa dynamic debate  [arxiv](https://arxiv.org/pdf/2110.06025.pdf) |

### Tema 2: URL/Domain-based Phishing Detection

| Nama | Tahun | Judul | Metode | Kesimpulan |
|---|---|---|---|---|
| IEEE | 2020 | Texception: A Character/Word-Level Deep Learning Model for Phishing URL Detection | Parallel convolutional layers (character + word level) | Texception mencapai 126.7% increase TPR at 0.01% FPR untuk internet-scale detection dengan pure URL-based approach tanpa external features  [ieeexplore.ieee](https://ieeexplore.ieee.org/document/9053670/) |
| Cendikia Inovasi | 2026 | High-Recall URL Phishing Detection via Multilayer Perceptron: Feature Selection, Learning Curves, and Confusion-Matrix Verification | MLP + ANOVA feature selection + imbalance handling | MLP dengan ANOVA feature selection mencapai accuracy 99.98% dengan stability tinggi, membuktikan pentingnya high recall untuk phishing detection  [cendikiainovasi](https://cendikiainovasi.org/BIMA/index.php/AI/article/view/9) |
| ACM | 2020 | Visualizing and Interpreting RNN Models in URL-based Phishing Detection | 4 RNN models + lexical features + visualization | Ensemble 4 RNN models mencapai accuracy >99% dengan visualization techniques untuk interpretability, namun black box nature masih ada  [dl.acm](https://dl.acm.org/doi/10.1145/3381991.3395602) |
| IEEE | 2020 | PhishHaven—An Efficient Real-Time AI Phishing URLs Detection System | Ensemble ML + lexical analysis + HTML Encoding + voting | PhishHaven mencapai 100% accuracy untuk AI-generated phishing dengan ensemble voting dan tiny URL handling, namun unbiased voting bisa fail pada equal votes  [ieeexplore.ieee](https://ieeexplore.ieee.org/document/9082616/) |
| EAI | 2022 | Learning to Detect Phishing Web Pages Using Lexical and String Complexity Analysis | Confidence weighted learning classifier | Confidence weighted learning mencapai accuracy 98.35% (FPR 0.026, FNR 0.005) dengan string complexity metrics untuk URL analysis  [eudl](http://eudl.eu/doi/10.4108/eai.20-4-2022.173950) |
| Nature | 2026 | Metadata driven malicious URL detection using RoBERTa large and multi source network threat intelligence | RoBERTa-Large + metadata + attention layers + SHAP/LIME | RoBERTa-Large dengan metadata mencapai accuracy 98% dan explainability via SHAP/LIME, membuktikan efektivitas LLM untuk URL detection  [nature](https://www.nature.com/articles/s41598-025-34790-x) |
| Baltic Journal | 2020 | Detection of Phishing URLs by Using Deep Learning Approach and Multiple Features Combinations | Combined CNN + LSTM (character + word embeddings) | CNN-LSTM hybrid dengan character dan word embeddings mencapai accuracy 94.4%, menunjukkan potensi hybrid feature approach  [bjmc.lu](http://www.bjmc.lu.lv/fileadmin/user_upload/lu_portal/projekti/bjmc/Contents/8_3_06_Rasymas.pdf) |

### Tema 3: LLM for Security Text Classification

| Nama | Tahun | Judul | Metode | Kesimpulan |
|---|---|---|---|---|
| arXiv | 2025 | SpaLLM-Guard: Pairing SMS Spam Detection Using Open-source and Commercial LLMs | Fine-tuned LLMs + few-shot learning | Fine-tuned LLMs dengan few-shot learning efektif mitigate concept drift pada evolving spam patterns, namun memerlukan computational cost tinggi  [arxiv](https://arxiv.org/pdf/2501.04985.pdf) |
| arXiv | 2025 | Leveraging Large Language Models for Cybersecurity: Enhancing SMS Spam Detection with Robust and Context-Aware Text Classification | Robust context-aware text classification dengan LLMs | LLMs memberikan reliable performance untuk SMS spam detection dengan TF-IDF + classifiers, membuktikan foundation LLM-based text classification  [arxiv](https://arxiv.org/pdf/2502.11014.pdf) |
| IEEE | 2025 | A Hybrid NLP and Deep Learning Framework for Intelligent SMS Phishing (Smishing) Detection | LSTM + URL features + Random Forest (dual-input) | Hybrid LSTM-RF dengan dual-input (text + URL) mencapai accuracy 91.19% untuk smishing detection dengan shortened URL handling  [ieeexplore.ieee](https://ieeexplore.ieee.org/document/11346167/) |
| Wiley | 2024 | Enhancing Phishing Detection: A Machine Learning Approach to Predicting Malicious Emails, URLs, and SMS Messages | 9 ML/DL models + ensemble approach | Ensemble approach dengan SVM (99.91%) dan BiGRU (99.75%) efektif untuk multi-modal phishing detection across emails, URLs, dan SMS  [onlinelibrary.wiley](https://onlinelibrary.wiley.com/doi/10.1155/acis/6633979) |
| ACM | 2021 | Hybrid CNN-GRU Framework with Integrated Pre-trained Language Transformer for SMS Phishing Detection | MPNet (pre-trained) + CNN + Bi-GRU hybrid | Hybrid MPNet-CNN-GRU outperforms individual ML/DL models untuk SMS phishing, membuktikan efektivitas pre-trained transformer untuk unstructured text  [dl.acm](https://dl.acm.org/doi/10.1145/3508072.3508109) |
| UIN Suska | 2025 | SMS Phishing Detection Model with Hyperparameter Optimization in Machine Learning | 10 algorithms + Grid Search + Optuna optimization | SVM & Logistic Regression mencapai accuracy 98.5% dengan hyperparameter optimization, menunjukkan pentingnya tuning untuk Indonesian SMS context  [ejournal.uin-suska.ac](https://ejournal.uin-suska.ac.id/index.php/coreit/article/view/35547) |

### Tema 4: Multi-Agent Debate for Decision Making

| Nama | Tahun | Judul | Metode | Kesimpulan |
|---|---|---|---|---|
| arXiv | 2025 | MALLM: Multi-Agent Large Language Models Framework | 144+ MAD configurations (personas, generators, paradigms, protocols) | MALLM framework menyediakan systematic analysis untuk MAD components dengan 144+ configurations, menjadi foundation untuk MAD implementation  [arxiv](https://arxiv.org/abs/2509.11656) |
| arXiv | 2024 | Encouraging Divergent Thinking in Large Language Models through Multi-Agent Debate | MAD framework: "tit for tat" arguments + judge | MAD dengan "tit for tat" debate dan judge berhasil solve Depth-of-Thought problem, menjadi seminal paper untuk multi-agent debate concept  [arxiv](http://arxiv.org/pdf/2305.19118.pdf) |
| arXiv | 2025 | Free-MAD: Consensus-Free Multi-Agent Debate | Score-based decision + anti-conformity + single-round debate | Free-MAD dengan score-based dan anti-conformity mencapai significant improvement dengan reduced token overhead via single-round debate  [arxiv](https://arxiv.org/abs/2509.11035) |
| arXiv | 2024 | ReConcile: Round-Table Conference Improves Reasoning via Consensus among Diverse LLMs | Multi-model multi-agent + confidence-weighted voting | ReConcile dengan confidence-weighted voting pada diverse LLMs enhanced collaborative reasoning via consensus mechanism  [arxiv](http://arxiv.org/pdf/2309.13007.pdf) |
| ACL Findings | 2025 | CONSENSAGENT: Towards Efficient and Effective Consensus in Multi-Agent LLM Interactions Through Sycophancy Mitigation | Dynamic prompt refinement berdasarkan agent interactions | CONSENSAGENT mencapai state-of-the-art results dengan mitigate sycophancy problem via dynamic prompt refinement, critical untuk MAD reliability  [aclanthology](https://aclanthology.org/2025.findings-acl.1141) |
| IEEE | 2024 | ConfidenceCal: Enhancing LLMs Reliability through Confidence Calibration in Multi-Agent Debate | Calibrated confidence + attention mechanism adjustment | ConfidenceCal dengan calibrated confidence reduced misleading confidence dan increased trustworthiness dalam multi-agent debate  [ieeexplore.ieee](https://ieeexplore.ieee.org/document/10808396/) |
| IEEE | 2025 | Debate-to-Decide: A Deliberative Multi-Agent Framework for Fair and Explainable Student Credit Scoring | LLM agents debate + formal argumentation theory | Debate-to-Decide mencapai superior accuracy dan F1 dengan lower bias, membuktikan "glass-box" paradigm untuk explainable decision making  [ieeexplore.ieee](https://ieeexplore.ieee.org/document/11365220/) |
| arXiv | 2025 | Diversity of Thought Elicits Stronger Reasoning Capabilities in Multi-Agent Debate Frameworks | Multi-agent debate dengan diversity emphasis | Diversity dalam multi-agent debate improves reasoning at any model scale, membuktikan pentingnya agent diversity untuk debate quality  [arxiv](http://arxiv.org/pdf/2410.12853.pdf) |
| arXiv | 2024 | Enhancing Multi-Agent Consensus through Third-Party LLM Integration: Analyzing Uncertainty and Mitigating Hallucinations | Third-party LLM + uncertainty estimation + confidence analysis | Third-party LLM dengan uncertainty estimation optimized consensus formation via attention weights, menunjukkan judge/arbitrator role importance  [arxiv](http://arxiv.org/pdf/2411.16189.pdf) |

### Paper Pendukung Metodologi Evaluasi

| Nama | Tahun | Judul | Metode | Kesimpulan |
|---|---|---|---|---|
| IEEE | 2020 | Analysis of Phishing Website Detection Using CNN and Bidirectional LSTM | CNN + Bidirectional LSTM | CNN-BiLSTM menyediakan standard evaluation framework dengan accuracy, precision, recall metrics untuk phishing detection  [ieeexplore.ieee](https://ieeexplore.ieee.org/document/9297395/) |
| Emerald | 2020 | Intelligent phishing detection scheme using deep learning algorithms | Deep learning algorithms | Deep learning dengan sensitivity analysis dan misclassification counting menyediakan comprehensive error analysis methodology  [emerald](http://www.emerald.com/jeim/article/36/3/747-766/203279) |
| arXiv | 2024 | Should we be going MAD? A Look at Multi-Agent Debate Strategies for LLMs | Comparative analysis of MAD strategies | Comparative analysis menunjukkan cost, time, accuracy trade-offs untuk berbagai MAD strategies, penting untuk benchmarking  [arxiv](http://arxiv.org/pdf/2311.17371.pdf) |

***

**Total: 33 paper**

Format ini lebih ringkas dan siap untuk BAB 2 thesis kamu! 📋