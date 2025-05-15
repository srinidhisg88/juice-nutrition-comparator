# Juice Nutrition Comparator

A FastAPI application that allows users to upload an image of a juice's nutritional label. The app performs Optical Character Recognition (OCR) on the image to extract key nutritional values, compares the juice with others from a predefined database, and provides a natural language suggestion for a healthier choice.

## Features

- **OCR-based extraction**: Uses Tesseract to read nutritional labels from juice packaging images.
- **Juice comparison**: Compares extracted nutritional data with other juices from a database (e.g., sugar, calories, preservatives).
- **Groq LLM integration**: Sends comparison results to a large language model (LLM) to suggest a healthier juice in natural language.
- **PostgreSQL database**: Uses Supabase to store juice data for comparison.

## Requirements

- Python 3.10 or higher
- PostgreSQL or Supabase for juice data storage
- Tesseract OCR (must be installed locally or in the deployment environment)

## Installation

1. Clone the repository:

```bash
git clone https://github.com/your-username/juice-nutrition-comparator.git
cd juice-nutrition-comparator