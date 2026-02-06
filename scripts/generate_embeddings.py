#!/usr/bin/env python3
"""
Generate 2D coordinates for semantic map visualization from Factually dataset.
Uses sentence-transformers for embeddings and UMAP for dimensionality reduction.
"""

import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
import umap
import warnings
warnings.filterwarnings('ignore')

# Configuration
INPUT_FILE = '/Users/wongpeiting/Desktop/CU/python-work/semantic-map-factually/to-sync/factually_corrections_and_clarifications.csv'
OUTPUT_FILE = '/Users/wongpeiting/Desktop/CU/python-work/semantic-map-factually/factually_with_coordinates.csv'

# Load the data
print("Loading data...")
df = pd.read_csv(INPUT_FILE)
print(f"Loaded {len(df)} rows")
print(f"Columns: {df.columns.tolist()}")

# Prepare text for embedding - combine title, summary, and article_text for richer semantic representation
def prepare_text(row):
    parts = []
    if pd.notna(row.get('title')):
        parts.append(str(row['title']))
    if pd.notna(row.get('summary')):
        parts.append(str(row['summary']))
    if pd.notna(row.get('article_text')):
        # Use first 1000 characters of article to avoid very long texts
        article = str(row['article_text'])[:2000]
        parts.append(article)
    return ' '.join(parts)

df['combined_text'] = df.apply(prepare_text, axis=1)
print(f"\nSample combined text length: {len(df['combined_text'].iloc[0])} characters")

# Load sentence transformer model
print("\nLoading sentence-transformers model...")
model = SentenceTransformer('all-MiniLM-L6-v2')  # Fast and effective model

# Generate embeddings
print("Generating embeddings...")
texts = df['combined_text'].tolist()
embeddings = model.encode(texts, show_progress_bar=True, batch_size=32)
print(f"Embedding shape: {embeddings.shape}")

# Apply UMAP for dimensionality reduction
print("\nApplying UMAP for 2D reduction...")
reducer = umap.UMAP(
    n_neighbors=15,
    min_dist=0.1,
    n_components=2,
    metric='cosine',
    random_state=42
)
coords_2d = reducer.fit_transform(embeddings)
print(f"2D coordinates shape: {coords_2d.shape}")

# Add coordinates to dataframe
df['x'] = coords_2d[:, 0]
df['y'] = coords_2d[:, 1]

# Drop the combined_text column (not needed in output)
df = df.drop(columns=['combined_text'])

# Save to CSV
print(f"\nSaving to {OUTPUT_FILE}...")
df.to_csv(OUTPUT_FILE, index=False)
print(f"Saved {len(df)} rows with x,y coordinates")

# Print summary statistics
print("\nCoordinate statistics:")
print(f"  x: min={df['x'].min():.2f}, max={df['x'].max():.2f}, mean={df['x'].mean():.2f}")
print(f"  y: min={df['y'].min():.2f}, max={df['y'].max():.2f}, mean={df['y'].mean():.2f}")

# Preview output
print("\nPreview of output:")
print(df[['date', 'title', 'x', 'y']].head(10).to_string())
