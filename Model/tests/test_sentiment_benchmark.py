import os
import pytest
import pandas as pd
import numpy as np
from Model.sentiment.analyzer import SentimentAnalyzerSuite
from Model.sentiment.benchmarker import run_sentiment_benchmark

def test_sentiment_analyzer_suite():
    suite = SentimentAnalyzerSuite()
    
    label, score = suite.predict_lexicon("pantai ini sangat bagus indah dan bersih")
    assert label == "positive"
    assert score == 1.0

    label_neg, score_neg = suite.predict_lexicon("tempatnya sangat kotor bau dan buruk")
    assert label_neg == "negative"
    assert score_neg == -1.0

def test_run_sentiment_benchmark():
    df_res = run_sentiment_benchmark(output_csv="reports/benchmark_sentiment_results.csv")
    assert len(df_res) == 3
    assert "accuracy" in df_res.columns
    assert "macro_f1" in df_res.columns
    assert "latency_per_sample_ms" in df_res.columns

    c3_acc = df_res[df_res["algorithm"].str.contains("Candidate 3")]["accuracy"].values[0]
    assert c3_acc > 0.80
