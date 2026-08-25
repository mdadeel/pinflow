# Pinterest AI Pinterest Publisher — Complete Build Specification

## Objective

Build a production-ready Python application that automatically processes AI-generated images, generates Pinterest-optimized metadata using OpenRouter AI models, stores content in a local database, and publishes or schedules Pins through the Pinterest API.

The system must be modular, scalable, configurable, and designed for handling thousands of Pins.

---

# Core Goal

Given a folder containing images:

```text
/images
    wallpaper_001.png
    wallpaper_002.png
    wallpaper_003.png
```

The application should automatically:

1. Detect new images.
2. Analyze images using a Vision AI model through OpenRouter.
3. Generate:
   - Pinterest Title
   - Pinterest Description
   - Alt Text
   - Primary Keyword
   - Secondary Keywords
   - Pinterest Tags
   - Board Recommendation
   - Content Category
4. Store metadata in SQLite.
5. Upload Pins to Pinterest.
6. Schedule publishing.
7. Track publishing status.
8. Avoid duplicate uploads.
9. Support bulk processing.
10. Provide analytics and reporting.

---

# Technical Stack

## Backend

- Python 3.12+
- FastAPI
- SQLAlchemy
- SQLite
- Pydantic
- APScheduler

## APIs

### OpenRouter

Used for:

- Image analysis
- Metadata generation
- Categorization
- SEO optimization

### Pinterest API

Used for:

- Pin creation
- Board retrieval
- Publishing
- Analytics

---

# Project Structure

```text
pinterest_automation/

├── app/
│
├── api/
│   ├── pinterest.py
│   ├── openrouter.py
│
├── services/
│   ├── image_analyzer.py
│   ├── seo_generator.py
│   ├── scheduler.py
│   ├── analytics.py
│
├── database/
│   ├── models.py
│   ├── db.py
│
├── processors/
│   ├── image_watcher.py
│   ├── uploader.py
│
├── prompts/
│   ├── pinterest_seo.txt
│
├── storage/
│   ├── images/
│
├── logs/
│
├── config/
│   ├── settings.py
│
├── dashboard/
│
├── main.py
│
└── requirements.txt
```

---

# Database Schema

Create SQLite schema.

## Pins Table

```sql
id
image_path
image_hash
title
description
alt_text
primary_keyword
secondary_keywords
tags
board_name
content_category
status
scheduled_time
published_time
pin_url
created_at
updated_at
```

---

## Analytics Table

```sql
id
pin_id
impressions
clicks
saves
outbound_clicks
last_updated
```

---

# Image Processing Pipeline

## Step 1

Watch image folder continuously.

Detect:

- png
- jpg
- jpeg
- webp

Ignore duplicates.

Use image hash comparison.

---

## Step 2

Send image to OpenRouter Vision Model.

Default model:

```text
google/gemini-2.5-flash
```

Allow model selection from config.

---

# AI Prompt Requirements

For every image generate:

## Pinterest Title

Requirements:

- 60–100 characters
- SEO optimized
- Natural language
- High CTR

---

## Pinterest Description

Requirements:

- 300–500 characters
- Keyword rich
- Human readable
- Not spammy

---

## Alt Text

Requirements:

- Accessibility friendly
- Accurate image description

---

## Keywords

Generate:

### Primary Keyword

Single keyword.

### Secondary Keywords

10–20 keywords.

---

## Tags

Generate:

15–25 Pinterest tags.

---

## Board Recommendation

Choose best matching board.

Examples:

```text
Anime Wallpapers
Minimalist Wallpapers
Aesthetic Art
Relationship Quotes
Couple Wallpapers
Dark Anime
Phone Backgrounds
Desktop Wallpapers
```

---

## Content Category

Examples:

```text
Anime
Wallpaper
Aesthetic
Motivation
Relationship
Quotes
Gaming
Technology
Nature
```

---

# Required AI Output Format

Return strict JSON only.

Example:

```json
{
  "title": "",
  "description": "",
  "alt_text": "",
  "primary_keyword": "",
  "secondary_keywords": [],
  "tags": [],
  "board": "",
  "category": ""
}
```

Validate before saving.

---

# Pinterest Publishing System

Implement:

## Board Management

Fetch all boards.

Allow:

- Auto mapping
- Manual mapping

Example:

```text
Anime Wallpapers → Anime Board
Couple Wallpapers → Relationship Board
```

---

## Pin Creation

Upload:

- Image
- Title
- Description
- Alt Text
- Destination URL (optional)

---

## Scheduling

Support:

- Immediate publishing
- Scheduled publishing

Scheduler must survive application restarts.

Store schedule in database.

---

# Bulk Processing

Support:

```text
10 images
100 images
1,000 images
10,000 images
```

Must process in batches.

Configurable batch size.

Example:

```python
BATCH_SIZE = 25
```

---

# Dashboard

Build a web dashboard.

Features:

## Overview

Display:

- Total images
- Pending Pins
- Scheduled Pins
- Published Pins
- Failed Pins

---

## Image Library

Display:

- Thumbnail
- Status
- Generated metadata

---

## Scheduler View

Calendar view.

Show:

- Upcoming Pins
- Published Pins

---

## Analytics View

Display:

- Impressions
- Saves
- Clicks
- CTR
- Top Performing Pins

---

# Configuration System

Use environment variables.

```env
OPENROUTER_API_KEY=
PINTEREST_ACCESS_TOKEN=
PINTEREST_BOARD_ID=
OPENROUTER_MODEL=
BATCH_SIZE=
POSTS_PER_DAY=
```

---

# Posting Strategy Engine

Implement intelligent scheduling.

Default:

```text
5–10 Pins per day
```

Spread across:

```text
08:00
11:00
14:00
17:00
20:00
```

Configurable.

Avoid posting all Pins at once.

---

# Duplicate Prevention

Prevent:

- Duplicate images
- Duplicate titles
- Duplicate uploads

Use:

- SHA256 image hashing
- Database checks

---

# Error Handling

Implement:

- API retries
- Rate limit handling
- Failed upload recovery
- Logging

Store all errors in logs.

---

# Reporting

Generate reports:

## Daily

- Pins posted
- Failed uploads
- API usage

## Weekly

- Top performing categories
- Best keywords
- Best boards

---

# Future Expansion

Architecture should support future additions:

- Instagram
- Facebook
- Threads
- X/Twitter
- Tumblr
- Reddit

Through plugin-based publishing modules.

---

# Expected Outcome

The final product should function as a fully automated Pinterest content publishing platform that:

- Reads AI-generated images.
- Generates SEO metadata automatically.
- Stores all content locally.
- Schedules Pins intelligently.
- Publishes through Pinterest API.
- Tracks analytics.
- Scales to thousands of Pins with minimal human involvement.