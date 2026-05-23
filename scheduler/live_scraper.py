import schedule
import time
import subprocess
import sys
from datetime import datetime
print(sys.executable)
PYTHON_PATH = r"C:\Users\koush\disastro_model\ai_env\Scripts\python.exe"


def run_pipeline():

    print("\n========================")
    print("PIPELINE STARTED")
    print("Time:", datetime.now())
    print("========================\n")

    subprocess.run(
    [
        PYTHON_PATH,
        "-c",
        "import sys; print(sys.executable)"
    ]
    )
    print("STEP 1 : SCRAPING")
    subprocess.run(
        [
            "scrapy",
            "crawl",
            "bbc_news",
            "-O",
            "disastro_scraper/bbc_news.json"
        ]
    )


    print("STEP 2 : CLEANING")
    subprocess.run(
        [
            PYTHON_PATH,
            "-u",
            "preprocessing/clean_text.py"
        ]
    )


    print("STEP 3 : EMBEDDINGS")
    subprocess.run(
        [
            PYTHON_PATH,
            "-u",
            "embeddings/generate_embedding.py"
        ]
    )


    print("STEP 4 : VECTOR STORAGE")
    subprocess.run(
        [
            PYTHON_PATH,
            "-u",
            "vectordb/store_embedding.py"
        ]
    )


    print("STEP 5 : RAG GENERATION")
    subprocess.run(
        [
            PYTHON_PATH,
            "-u",
            "rag/rag_pipeline.py"
        ]
    )


    print("\n========================")
    print("PIPELINE FINISHED")
    print("Time:", datetime.now())
    print("========================\n")


schedule.every(1).minutes.do(run_pipeline)

print("AI pipeline started...")


run_pipeline()


while True:

    schedule.run_pending()

    time.sleep(1)