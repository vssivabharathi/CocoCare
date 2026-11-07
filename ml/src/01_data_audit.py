from pathlib import Path
from PIL import Image
from collections import Counter
import pandas as pd


IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"
}


def inspect_dataset(dataset_path):
    dataset_path = Path(dataset_path)

    records = []
    corrupted = []

    for class_dir in sorted(dataset_path.iterdir()):

        if not class_dir.is_dir():
            continue

        class_name = class_dir.name

        for image_path in class_dir.rglob("*"):

            if image_path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue

            try:
                with Image.open(image_path) as img:

                    width, height = img.size
                    mode = img.mode

                    records.append({
                        "file": str(image_path),
                        "class": class_name,
                        "width": width,
                        "height": height,
                        "mode": mode
                    })

            except Exception:
                corrupted.append(str(image_path))

    return pd.DataFrame(records), corrupted


def print_report(name, df, corrupted):

    print("\n" + "=" * 60)
    print(f"DATASET: {name}")
    print("=" * 60)

    print(f"\nTotal images: {len(df)}")
    print(f"Corrupted images: {len(corrupted)}")

    print("\nClasses:")
    print(df["class"].value_counts())

    print("\nImage dimensions:")
    print(df[["width", "height"]].describe())

    print("\nColor modes:")
    print(df["mode"].value_counts())


if __name__ == "__main__":

    datasets = {
        "Mendeley": "../data/raw/mendeley",
        "Kaggle": "../data/raw/kaggle"
    }

    for name, path in datasets.items():

        df, corrupted = inspect_dataset(path)

        print_report(name, df, corrupted)

        output_path = f"../results/{name.lower()}_dataset_metadata.csv"

        df.to_csv(output_path, index=False)

        print(f"\nMetadata saved to: {output_path}")