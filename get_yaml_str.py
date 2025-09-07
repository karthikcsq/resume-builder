import json
import yaml


def main():
    in_path = "resume_truth.yaml"
    try:
        with open(in_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"YAML not found: {in_path}")
        return
    except Exception as e:
        print(f"Failed to read/parse YAML: {e}")
        return

    # Dump pretty JSON, preserving unicode
    print(json.dumps(data, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
