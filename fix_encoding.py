#!/usr/bin/env python3
"""Fix encoding issues in the data files."""

import pandas as pd

# Read the source file
df = pd.read_csv('factually_with_coordinates.csv')

# Function to fix encoding issues
def fix_encoding(text):
    if pd.isna(text):
        return text
    text = str(text)

    # Fix mojibake patterns (UTF-8 incorrectly decoded)
    # These are the byte sequences that appear when UTF-8 is read as latin-1/cp1252
    mojibake_fixes = {
        b'\xe2\x80\x99'.decode('utf-8'): "'",  # Right single quote
        b'\xe2\x80\x98'.decode('utf-8'): "'",  # Left single quote
        b'\xe2\x80\x9c'.decode('utf-8'): '"',  # Left double quote
        b'\xe2\x80\x9d'.decode('utf-8'): '"',  # Right double quote
        b'\xe2\x80\x93'.decode('utf-8'): '-',  # En dash
        b'\xe2\x80\x94'.decode('utf-8'): '-',  # Em dash
        b'\xe2\x80\xa6'.decode('utf-8'): '...', # Ellipsis
        b'\xc2\xa0'.decode('utf-8'): ' ',      # Non-breaking space
    }

    for bad, good in mojibake_fixes.items():
        text = text.replace(bad, good)

    # Also handle the corrupted versions that show as '€ patterns
    # These happen when UTF-8 bytes are misinterpreted
    text = text.replace('\u2019', "'")
    text = text.replace('\u2018', "'")
    text = text.replace('\u201c', '"')
    text = text.replace('\u201d', '"')
    text = text.replace('\u2013', '-')
    text = text.replace('\u2014', '-')
    text = text.replace('\u2026', '...')
    text = text.replace('\u00a0', ' ')

    return text

# Apply to text columns
for col in ['article_text', 'title', 'summary']:
    if col in df.columns:
        print(f'Fixing {col}...')
        df[col] = df[col].apply(fix_encoding)

# Save back to source
df.to_csv('factually_with_coordinates.csv', index=False)
print('Saved factually_with_coordinates.csv')

# Also save to public/data.csv
df.to_csv('public/data.csv', index=False)
print('Saved public/data.csv')

# Verify
print('\nVerifying - searching for problematic characters...')
for col in ['article_text', 'title', 'summary']:
    if col in df.columns:
        # Check for remaining issues
        issues = df[df[col].astype(str).str.contains('\u2019|\u201c|\u201d', regex=True, na=False)]
        if len(issues) > 0:
            print(f'  {col}: {len(issues)} rows still have issues')
        else:
            print(f'  {col}: OK')

print('\nDone!')
