"""
Behavioral Anomaly Detector
Detect deviations from user's established baseline behavior
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class AnomalyResult:
    """Result of behavioral anomaly detection"""
    is_anomaly: bool
    anomaly_type: str
    description: str
    deviation_score: float  # 0.0-1.0
    baseline_value: Any
    current_value: Any


class BehavioralAnomalyDetector:
    """
    Detect behavioral anomalies by comparing current message
    against user's established baseline.
    """
    
    # Thresholds for anomaly detection
    TIME_ANOMALY_THRESHOLD = 2  # Hours outside typical range
    LENGTH_DEVIATION_THRESHOLD = 2.0  # Standard deviations
    STYLE_DEVIATION_THRESHOLD = 0.3  # 30% deviation
    
    def __init__(self):
        pass
    
    def check_time_anomaly(
        self,
        message_hour: int,
        typical_hours: list[int]
    ) -> AnomalyResult | None:
        """
        Periksa apakah pesan dikirim pada waktu yang tidak biasa.
        
        Args:
            message_hour: Jam (0-23) saat pesan dikirim
            typical_hours: Daftar jam ketika user biasanya posting
            
        Returns:
            AnomalyResult jika anomali terdeteksi, None sebaliknya
        """
        if not typical_hours:
            return None
        
        # Check if current hour is in typical range
        if message_hour in typical_hours:
            return None
        
        # Calculate distance to nearest typical hour
        min_distance = min(
            min(abs(message_hour - h), 24 - abs(message_hour - h))
            for h in typical_hours
        )
        
        if min_distance >= self.TIME_ANOMALY_THRESHOLD:
            # Calculate deviation score (0-1)
            deviation_score = min(min_distance / 12, 1.0)
            
            return AnomalyResult(
                is_anomaly=True,
                anomaly_type="time_anomaly",
                description=f"Message sent at unusual hour ({message_hour}:00)",
                deviation_score=deviation_score,
                baseline_value=typical_hours,
                current_value=message_hour
            )
        
        return None
    
    def check_length_anomaly(
        self,
        message_length: int,
        avg_length: float,
        std_length: float = None
    ) -> AnomalyResult | None:
        """
        Periksa apakah panjang pesan signifikan menyimpang dari baseline.
        
        Args:
            message_length: Panjang pesan saat ini
            avg_length: Rata-rata panjang pesan user
            std_length: Standard deviation (jika tidak disediakan, gunakan 30% dari avg)
            
        Returns:
            AnomalyResult jika anomali terdeteksi, None sebaliknya
        """
        if not avg_length or avg_length == 0:
            return None
        
        # Estimate std if not provided
        if std_length is None or std_length == 0:
            std_length = avg_length * 0.3
        
        # Calculate z-score
        z_score = abs(message_length - avg_length) / std_length
        
        if z_score >= self.LENGTH_DEVIATION_THRESHOLD:
            deviation_score = min(z_score / 5, 1.0)
            
            direction = "longer" if message_length > avg_length else "shorter"
            
            return AnomalyResult(
                is_anomaly=True,
                anomaly_type="length_anomaly",
                description=f"Message is significantly {direction} than usual",
                deviation_score=deviation_score,
                baseline_value=avg_length,
                current_value=message_length
            )
        
        return None
    
    def check_first_time_url(
        self,
        has_url: bool,
        url_sharing_rate: float,
        total_messages: int
    ) -> AnomalyResult | None:
        """
        Periksa apakah ini adalah pertama kali user membagikan URL.
        
        Args:
            has_url: Apakah pesan saat ini berisi URL
            url_sharing_rate: Tingkat historical URL sharing dari user
            total_messages: Total pesan dari user ini
            
        Returns:
            AnomalyResult jika sharing URL ini tidak biasa
        """
        if not has_url:
            return None
        
        # If user has never shared URLs before and has enough history
        if url_sharing_rate == 0 and total_messages >= 10:
            return AnomalyResult(
                is_anomaly=True,
                anomaly_type="first_time_url",
                description="User sharing URL for first time",
                deviation_score=0.7,
                baseline_value=url_sharing_rate,
                current_value=1
            )
        
        return None
    
    def check_emoji_anomaly(
        self,
        current_emoji_rate: float,
        baseline_emoji_rate: float
    ) -> AnomalyResult | None:
        """
        Periksa apakah penggunaan emoji signifikan berbeda dari baseline.
        
        Args:
            current_emoji_rate: Emoji rate dalam pesan saat ini
            baseline_emoji_rate: Typical emoji rate dari user
            
        Returns:
            AnomalyResult jika anomali terdeteksi
        """
        if baseline_emoji_rate == 0 and current_emoji_rate == 0:
            return None
        
        # Calculate relative difference
        if baseline_emoji_rate == 0:
            diff = current_emoji_rate
        else:
            diff = abs(current_emoji_rate - baseline_emoji_rate) / max(baseline_emoji_rate, 0.01)
        
        if diff >= self.STYLE_DEVIATION_THRESHOLD:
            return AnomalyResult(
                is_anomaly=True,
                anomaly_type="emoji_anomaly",
                description="Unusual emoji usage pattern",
                deviation_score=min(diff, 1.0),
                baseline_value=baseline_emoji_rate,
                current_value=current_emoji_rate
            )
        
        return None
    
    def analyze_all(
        self,
        message_text: str,
        message_timestamp: datetime,
        has_url: bool,
        baseline_metrics: dict
    ) -> list[AnomalyResult]:
        """
        Jalankan semua pengecekan anomali terhadap baseline user.
        
        Args:
            message_text: Isi pesan
            message_timestamp: Waktu pesan dikirim
            has_url: Apakah pesan mengandung URLs
            baseline_metrics: Metrik baseline user dari database
            
        Returns:
            Daftar anomali yang terdeteksi
        """
        anomalies = []
        
        if not baseline_metrics:
            return anomalies
        
        # Time anomaly
        time_result = self.check_time_anomaly(
            message_timestamp.hour,
            baseline_metrics.get("typical_hours", [])
        )
        if time_result:
            anomalies.append(time_result)
        
        # Length anomaly
        length_result = self.check_length_anomaly(
            len(message_text),
            baseline_metrics.get("avg_message_length", 0)
        )
        if length_result:
            anomalies.append(length_result)
        
        # First-time URL
        url_result = self.check_first_time_url(
            has_url,
            baseline_metrics.get("url_sharing_rate", 0),
            baseline_metrics.get("total_messages", 0)
        )
        if url_result:
            anomalies.append(url_result)
        
        # Emoji anomaly
        current_emoji_rate = self._calculate_emoji_rate(message_text)
        emoji_result = self.check_emoji_anomaly(
            current_emoji_rate,
            baseline_metrics.get("emoji_usage_rate", 0)
        )
        if emoji_result:
            anomalies.append(emoji_result)
        
        return anomalies
    
    def _calculate_emoji_rate(self, text: str) -> float:
        """Calculate emoji rate in text"""
        if not text:
            return 0.0
        
        import re
        # Regex for emojis
        emoji_pattern = re.compile(
            "[\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"   # symbols & pictographs
            "\U0001F680-\U0001F6FF"   # transport & map symbols
            "\U0001F1E0-\U0001F1FF"   # flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE
        )
        
        emojis = emoji_pattern.findall(text)
        emoji_count = sum(len(e) for e in emojis)
        
        return emoji_count / len(text) if text else 0.0
