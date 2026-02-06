#!/usr/bin/env python3
"""
Regenerate data.csv - preserves existing columns (topic, target, year, cluster) if present.
Only regenerates missing columns.
"""

import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from collections import Counter
import re

# Load the coordinates file
print("Loading factually_with_coordinates.csv...")
df = pd.read_csv('/Users/wongpeiting/Desktop/CU/python-work/semantic-map-factually/factually_with_coordinates.csv')
print(f"Loaded {len(df)} rows")
print(f"Existing columns: {list(df.columns)}")

# Clean up article text - fix encoding issues
print("\nCleaning article text...")
def clean_text(text):
    if pd.isna(text):
        return text
    text = str(text)
    # Fix common encoding issues - Unicode smart quotes to ASCII
    text = text.replace('\u2019', "'")
    text = text.replace('\u2018', "'")
    text = text.replace('\u201c', '"')
    text = text.replace('\u201d', '"')
    text = text.replace('\u2013', '-')
    text = text.replace('\u2014', '-')
    text = text.replace('\u2026', '...')
    text = text.replace('\u00a0', ' ')
    text = text.replace(''', "'")
    text = text.replace(''', "'")
    text = text.replace('"', '"')
    text = text.replace('"', '"')
    text = text.replace('–', '-')
    text = text.replace('—', '-')
    text = text.replace('…', '...')
    text = text.replace('Â', '')
    return text

for col in ['article_text', 'title', 'summary']:
    if col in df.columns:
        df[col] = df[col].apply(clean_text)

# Fix date format and extract year (only if year column doesn't exist)
print("\nProcessing dates...")
def parse_date(date_str):
    try:
        return pd.to_datetime(date_str, format='%d %B %Y')
    except:
        try:
            return pd.to_datetime(date_str)
        except:
            return pd.NaT

df['date'] = df['date'].apply(parse_date)

if 'year' not in df.columns or df['year'].isna().all():
    print("  Generating year column...")
    df['year'] = df['date'].dt.year.astype('Int64')
else:
    print("  Year column exists, preserving...")

# Only regenerate cluster/topic if they don't exist
if 'cluster' not in df.columns or 'topic' not in df.columns:
    print("\nPerforming K-means clustering...")
    coords = df[['x', 'y']].values
    n_clusters = 8
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    df['cluster'] = kmeans.fit_predict(coords)

    print("Generating topic labels...")
    def extract_keywords(texts):
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been', 'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need', 'dare', 'ought', 'used', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which', 'who', 'whom', 'whose', 'where', 'when', 'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just', 'also', 'now', 'here', 'there', 'then', 'once', 'if', 'unless', 'until', 'while', 'about', 'against', 'between', 'into', 'through', 'during', 'before', 'after', 'above', 'below', 'up', 'down', 'out', 'off', 'over', 'under', 'again', 'further', 'any', 'mr', 'ms', 'said', 'made', 'one', 'two', 'three', 'four', 'five', 'first', 'second', 'new', 'see', 'get', 'got', 'put', 'take', 'took', 'make', 'know', 'think', 'come', 'came', 'go', 'went', 'say', 'says', 'like', 'well', 'back', 'being', 'its', 'his', 'her', 'him', 'their', 'them', 'our', 'your', 'my'}
        word_counts = Counter()
        for text in texts:
            if pd.isna(text):
                continue
            words = re.findall(r'\b[A-Z][a-z]+\b', str(text))
            for word in words:
                if word.lower() not in stopwords and len(word) > 2:
                    word_counts[word] += 1
        return [word for word, count in word_counts.most_common(3)]

    cluster_labels = {}
    for cluster_id in range(n_clusters):
        cluster_texts = df[df['cluster'] == cluster_id]['article_text'].tolist()
        keywords = extract_keywords(cluster_texts)
        cluster_labels[cluster_id] = ', '.join(keywords) if keywords else f'Cluster {cluster_id}'

    df['topic'] = df['cluster'].map(cluster_labels)
else:
    print("\nCluster and topic columns exist, preserving...")

# Only regenerate target if it doesn't exist
if 'target' not in df.columns:
    print("\nExtracting targets...")
    # ... (target extraction code would go here)
    pass
else:
    print("\nTarget column exists, preserving...")

# Remove Workers' Party politicians from targets (they were never POFMA targets)
if 'target' in df.columns:
    def remove_wp_politicians(target):
        if pd.isna(target):
            return target
        parts = [p.strip() for p in str(target).split(';')
                 if 'Pritam Singh' not in p and 'Sylvia Lim' not in p and 'Low Thia Khiang' not in p]
        if not parts:
            return 'No target; Clarification'
        return '; '.join(parts)
    df['target'] = df['target'].apply(remove_wp_politicians)

# Convert date to ISO format string for CSV
df['date'] = df['date'].dt.strftime('%Y-%m-%d')

# Reorder columns
desired_order = ['date', 'title', 'summary', 'category', 'item_url', 'image_url', 'article_text', 'x', 'y', 'year', 'cluster', 'topic', 'target']
columns_order = [c for c in desired_order if c in df.columns]
# Add any extra columns not in desired order
for c in df.columns:
    if c not in columns_order:
        columns_order.append(c)
df = df[columns_order]

# Save to public/data.csv
output_path = '/Users/wongpeiting/Desktop/CU/python-work/semantic-map-factually/public/data.csv'
print(f"\nSaving to {output_path}...")
df.to_csv(output_path, index=False)
print(f"Saved {len(df)} rows")

# Print target distribution
if 'target' in df.columns:
    print("\nTarget distribution:")
    target_counts = df['target'].value_counts()
    for target, count in target_counts.head(20).items():
        print(f"  {target}: {count}")

# Generate cluster_labels.json only if we regenerated clusters
if 'cluster' in df.columns:
    print("\nGenerating cluster_labels.json...")
    import json

    cluster_labels_data = []
    for cluster_id in df['cluster'].unique():
        cluster_data = df[df['cluster'] == cluster_id]
        center_x = cluster_data['x'].mean()
        center_y = cluster_data['y'].mean()
        label = cluster_data['topic'].iloc[0] if 'topic' in cluster_data.columns else f'Cluster {cluster_id}'
        cluster_labels_data.append({
            'label': label,
            'x': float(center_x),
            'y': float(center_y),
            'count': len(cluster_data)
        })

    with open('/Users/wongpeiting/Desktop/CU/python-work/semantic-map-factually/public/cluster_labels.json', 'w') as f:
        json.dump(cluster_labels_data, f, indent=2)

print("\nDone!")
