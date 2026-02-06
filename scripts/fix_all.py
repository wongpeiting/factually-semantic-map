#!/usr/bin/env python3
"""Fix encoding issues and update targets."""

import pandas as pd
import re

# Load data
df = pd.read_csv('public/data.csv')

# Comprehensive encoding fix function
def fix_encoding(text):
    if pd.isna(text):
        return text
    text = str(text)

    # Fix the € pattern which appears in mojibake
    # Replace any sequence containing € that looks like corrupted quotes/apostrophes
    text = re.sub(r"'?€[™˜œ\u009d\u201d\u201c]?\s*", "'", text)
    text = re.sub(r"€\s*", "", text)  # Remove any remaining €

    # Unicode characters to ASCII
    text = text.replace('\u2019', "'")
    text = text.replace('\u2018', "'")
    text = text.replace('\u201c', '"')
    text = text.replace('\u201d', '"')
    text = text.replace('\u2013', '-')
    text = text.replace('\u2014', '-')
    text = text.replace('\u2026', '...')
    text = text.replace('\u00a0', ' ')

    return text

# Apply encoding fix to all text columns
print("Fixing encoding issues...")
for col in ['article_text', 'title', 'summary', 'target']:
    if col in df.columns:
        df[col] = df[col].apply(fix_encoding)
        print(f"  Fixed {col}")

# 1. Add Julie O'Connor to Shanmugam article
mask1 = df['title'].str.contains("Shanmugam's comments in Parliament on 4 October 2021", na=False)
print(f"\n1. Found {mask1.sum()} article(s) for Shanmugam 4 October 2021")
if mask1.sum() > 0:
    print(f"   Old target: {df.loc[mask1, 'target'].values[0]}")
    old_target = df.loc[mask1, 'target'].values[0]
    if "Julie O'Connor" not in str(old_target):
        df.loc[mask1, 'target'] = str(old_target) + "; Julie O'Connor"
    print(f"   New target: {df.loc[mask1, 'target'].values[0]}")

# 2. Shorten "National University of Singapore Society" to "NUSS" everywhere
print("\n2. Shortening 'National University of Singapore Society' to 'NUSS'...")
df['target'] = df['target'].str.replace('National University of Singapore Society', 'NUSS', regex=False)

# 3. Remove SDP from Thum Ping Tjin article
mask3 = df['title'].str.contains('Thum Ping Tjin', na=False)
print(f"\n3. Found {mask3.sum()} article(s) for Thum Ping Tjin")
if mask3.sum() > 0:
    print(f"   Old target: {df.loc[mask3, 'target'].values[0]}")
    old_target = df.loc[mask3, 'target'].values[0]
    parts = [p.strip() for p in str(old_target).split(';') if 'Singapore Democratic Party' not in p]
    df.loc[mask3, 'target'] = '; '.join(parts)
    print(f"   New target: {df.loc[mask3, 'target'].values[0]}")

# 4. Remove TOC from SDP article
mask4 = df['title'].str.contains('Falsehoods Posted By The Singapore Democratic Party', na=False)
print(f"\n4. Found {mask4.sum()} article(s) for SDP article")
if mask4.sum() > 0:
    print(f"   Old target: {df.loc[mask4, 'target'].values[0]}")
    old_target = df.loc[mask4, 'target'].values[0]
    parts = [p.strip() for p in str(old_target).split(';') if 'The Online Citizen' not in p]
    df.loc[mask4, 'target'] = '; '.join(parts)
    print(f"   New target: {df.loc[mask4, 'target'].values[0]}")

# Save to both files
df.to_csv('public/data.csv', index=False)
df.to_csv('factually_with_coordinates.csv', index=False)
print("\nSaved data files")

# Verify no encoding issues remain
print("\nVerifying encoding...")
for col in ['article_text', 'title', 'summary']:
    issues = df[df[col].astype(str).str.contains('€', na=False)]
    if len(issues) > 0:
        print(f"  WARNING: {col} still has {len(issues)} rows with euro sign")
    else:
        print(f"  {col}: OK")
