#!/usr/bin/env python3
"""
F.R.I.D.A.Y. Speech-to-Text Accuracy Benchmark

Measures Word Error Rate (WER) comparing:
1. English: local distil-whisper-small vs. local whisper-small-multilingual.
2. Hindi: local whisper-small-multilingual vs. cloud Sarvam AI Saaras v3 API.

Formula for Word Error Rate (WER):
    WER = (S + D + I) / N
where:
    S = Substitutions
    D = Deletions
    I = Insertions
    N = Number of words in ground truth reference.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def calculate_wer(reference: str, hypothesis: str) -> float:
    """
    Computes Word Error Rate using standard dynamic programming Levenshtein distance.
    """
    ref_words = reference.lower().split()
    hyp_words = hypothesis.lower().split()
    
    n = len(ref_words)
    m = len(hyp_words)
    
    if n == 0:
        return 1.0 if m > 0 else 0.0
        
    # Initialize DP matrix
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
        
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                sub = dp[i - 1][j - 1] + 1
                del_op = dp[i - 1][j] + 1
                ins = dp[i][j - 1] + 1
                dp[i][j] = min(sub, del_op, ins)
                
    return dp[n][m] / n


def run_accuracy_report():
    print("============================================================")
    print("F.R.I.D.A.Y. Speech-to-Text Accuracy & WER Benchmark")
    print("============================================================")
    print("This script defines ground-truth reference statements and calculates WER.")
    print("Record testing WAV samples on the host system to compute actual scores.")
    print()

    # Ground-truth reference lists
    english_references = [
        "What meetings do I have today",
        "Check my calendar for this afternoon",
        "How much storage is available on my Mac",
        "What is my battery percentage",
        "Read the file on my desktop called notes",
        "What time is it right now",
        "Set a reminder for tomorrow morning",
        "How much RAM is FRIDAY using",
        "What is the weather like today",
        "Open my documents folder",
    ]

    hindi_references = [
        "आज मेरी क्या मीटिंग है",
        "बैटरी कितनी बची है",
        "कितना स्टोरेज बाकी है",
        "अभी कितने बजे हैं",
        "मेरा आज का शेड्यूल क्या है",
    ]

    print("Reference English ground-truth statements:")
    for i, ref in enumerate(english_references, 1):
        print(f"  {i:02d}: '{ref}'")
    print()

    print("Reference Hindi ground-truth statements:")
    for i, ref in enumerate(hindi_references, 1):
        print(f"  {i:02d}: '{ref}'")
    print()

    # Example calculation
    ref_ex = "what meetings do i have today"
    hyp_ex = "what meeting do i have today"
    wer_ex = calculate_wer(ref_ex, hyp_ex)
    print(f"Example WER Calculation:")
    print(f"  Reference:  '{ref_ex}'")
    print(f"  Hypothesis: '{hyp_ex}'")
    print(f"  👉 Word Error Rate (WER): {wer_ex:.1%} (Lower is better)")
    print("=" * 60)


if __name__ == "__main__":
    run_accuracy_report()
