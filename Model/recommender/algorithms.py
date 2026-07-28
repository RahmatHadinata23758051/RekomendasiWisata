import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

class RecommenderAlgorithms:
    """
    Implements 4 Recommendation Algorithms for Head-to-Head Benchmarking:
    - Baseline 1: Simple Cosine Similarity
    - Baseline 2: Weighted Multi-Metric Similarity
    - Candidate 3: TF-IDF Feature Similarity + Quality Penalty
    - Candidate 4: Hybrid Multi-Objective Scoring Engine
    """
    def __init__(self, df_features):
        self.df = df_features.copy()
        self.n_items = len(self.df)

        # Extract vocabulary columns
        self.cat_cols = [c for c in self.df.columns if c.startswith("feat_cat_")]
        self.reg_cols = [c for c in self.df.columns if c.startswith("feat_reg_")]
        self.fac_cols = [c for c in self.df.columns if c.startswith("feat_fac_")]

        # Pre-extract matrices
        self.cat_matrix = self.df[self.cat_cols].values.astype(np.float32)
        self.reg_matrix = self.df[self.reg_cols].values.astype(np.float32)
        self.fac_matrix = self.df[self.fac_cols].values.astype(np.float32)

        # Full combined dense matrix for Baseline 1
        self.full_matrix = np.hstack([self.cat_matrix, self.reg_matrix, self.fac_matrix])

        # Eligibility mask (permanently closed attractions are excluded)
        self.eligible_mask = self.df["is_eligible_recommend"].values.astype(bool)

        # Quality penalties
        self.penalties = self.df["quality_penalty_score"].values.astype(np.float32)

        # TF-IDF representation for Candidate 3
        text_corpus = []
        for _, row in self.df.iterrows():
            c_name = str(row.get("primary_category", "")).replace("_", " ")
            r_name = str(row.get("city_or_regency", ""))
            fac_text = " ".join([col.replace("feat_fac_has_", "") for col in self.fac_cols if row[col] == 1.0])
            text_corpus.append(f"{c_name} {r_name} {fac_text}")
        
        self.tfidf_vectorizer = TfidfVectorizer()
        self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(text_corpus)

    def baseline1_simple_cosine(self, query_vector, top_k=10):
        """Baseline 1: Cosine Similarity on Full Combined Feature Matrix"""
        sims = cosine_similarity(query_vector.reshape(1, -1), self.full_matrix)[0]
        sims[~self.eligible_mask] = -1.0
        top_indices = np.argsort(sims)[::-1][:top_k]
        return top_indices, sims[top_indices]

    def baseline2_weighted_multimetric(self, query_cat, query_reg, query_fac, top_k=10,
                                       w_cat=0.5, w_reg=0.3, w_fac=0.2):
        """Baseline 2: Weighted Multi-Metric (Cosine Cat + Match Reg + Jaccard Fac)"""
        sim_cat = cosine_similarity(query_cat.reshape(1, -1), self.cat_matrix)[0]
        sim_reg = np.dot(self.reg_matrix, query_reg)
        
        # Jaccard for Facilities
        intersection = np.dot(self.fac_matrix, query_fac)
        union = np.sum(self.fac_matrix, axis=1) + np.sum(query_fac) - intersection
        sim_fac = np.divide(intersection, union, out=np.zeros_like(intersection, dtype=np.float32), where=union!=0)

        scores = w_cat * sim_cat + w_reg * sim_reg + w_fac * sim_fac
        scores[~self.eligible_mask] = -1.0
        top_indices = np.argsort(scores)[::-1][:top_k]
        return top_indices, scores[top_indices]

    def candidate3_tfidf_quality(self, query_text, top_k=10):
        """Candidate 3: TF-IDF Text Similarity - Quality Penalty"""
        q_vec = self.tfidf_vectorizer.transform([query_text])
        sims = cosine_similarity(q_vec, self.tfidf_matrix)[0]
        scores = sims - 0.5 * self.penalties
        scores[~self.eligible_mask] = -1.0
        top_indices = np.argsort(scores)[::-1][:top_k]
        return top_indices, scores[top_indices]

    def candidate4_hybrid_multi_objective(self, query_cat, query_reg, query_fac, user_lat=None, user_lng=None,
                                          top_k=10, w_cat=0.4, w_reg=0.25, w_fac=0.15, w_dist=0.10, w_qual=0.10):
        """Candidate 4: Hybrid Multi-Objective Scoring Engine"""
        sim_cat = cosine_similarity(query_cat.reshape(1, -1), self.cat_matrix)[0]
        sim_reg = np.dot(self.reg_matrix, query_reg)

        # Jaccard for Facilities
        intersection = np.dot(self.fac_matrix, query_fac)
        union = np.sum(self.fac_matrix, axis=1) + np.sum(query_fac) - intersection
        sim_fac = np.divide(intersection, union, out=np.zeros_like(intersection, dtype=np.float32), where=union!=0)

        # Geodesic Distance Decay
        if user_lat is not None and user_lng is not None:
            lats = self.df["latitude"].values
            lngs = self.df["longitude"].values
            # Approx Haversine distance in km
            d_lat = np.radians(lats - user_lat)
            d_lng = np.radians(lngs - user_lng)
            a = np.sin(d_lat / 2.0)**2 + np.cos(np.radians(user_lat)) * np.cos(np.radians(lats)) * np.sin(d_lng / 2.0)**2
            d_km = 2.0 * 6371.0 * np.arcsin(np.sqrt(a))
            sim_dist = np.exp(-0.015 * np.maximum(0.0, d_km - 5.0))
        else:
            sim_dist = np.ones(self.n_items, dtype=np.float32)

        # Quality bonus
        qual_score = (self.df["overall_completeness_score"].values / 100.0) - self.penalties

        scores = (w_cat * sim_cat + w_reg * sim_reg + w_fac * sim_fac + 
                  w_dist * sim_dist + w_qual * qual_score)
        
        scores[~self.eligible_mask] = -1.0
        top_indices = np.argsort(scores)[::-1][:top_k]
        return top_indices, scores[top_indices]
