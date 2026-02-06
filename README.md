# What's Being Fact-Checked?

A semantic map visualization of corrections and clarifications from [Factually.gov.sg](https://www.factually.gov.sg/), Singapore's state-run platform addressing online falsehoods.

**Link here:** https://wongpeiting.github.io/factually-semantic-map/

## About

This interactive visualization maps 124 fact-check articles on Factually as of Feb 5, 2026, allowing users to explore patterns in misinformation flagged by the Singapore government over time. Articles that cover similar themes are positioned closer together on the map, making it easy to identify clusters of related false claims. 

### How It Works

1. **Text Embeddings**: Each article's text is converted into a high-dimensional vector using sentence embeddings, capturing its semantic meaning.
2. **Dimensionality Reduction**: These vectors are projected into 2D space, preserving relative distances between similar articles.
3. **Clustering**: Articles are grouped into 8 broad categories using K-means clustering:
   - Justice (Death Penalty)
   - Governance (Election, Policies)
   - Finance (CPF & Reserves)
   - Employment (Cost of Living, Foreigners)
   - Law & Order (Police)
   - Housing (HDB, Prices)
   - Accountability (Ridout, Public Funds)
   - Health (Covid, Vaccines)

4. **Target Tagging**: Each article is tagged with the individuals or groups whose statements were corrected.

### Features

- **Search**: Find articles by keyword (supports pattern matching with `|` for "or" searches)
- **Filter by category**: Color-code and highlight by broad topic or target
- **Date range**: Filter articles by publication date, with markers for Singapore's General Elections
- **Click to pin**: Click any dot to pin its details in the side panel
- **Zoom & pan**: Navigate the map with mouse wheel and drag

## Data

The dataset includes corrections and clarifications from Factually.gov.sg covering the period from 2019 to 2025. Each row contains:
- Title and summary
- Full article text
- Publication date
- Target (who/what was corrected)
- Topic category
- 2D coordinates for visualization

## Development

```shell
npm install
npm run dev
```

## Deploy

```shell
npm run build
npm run deploy
```

## Credits

Built using the Tow Centre's semantic map template.

Data source: [Factually.gov.sg](https://www.factually.gov.sg/)