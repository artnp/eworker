import requests
import sys

# ทดสอบอัพโหลดไฟล์เล็กๆ ไป Litterbox
file_path = sys.argv[1] if len(sys.argv) > 1 else None

if not file_path:
    print("Usage: python test_litterbox.py <file_path>")
    sys.exit(1)

url = 'https://litterbox.catbox.moe/resources/internals/api.php'

print(f"Testing upload to Litterbox...")
print(f"File: {file_path}")

# Method 1: Simple file object (เหมือนเดิม)
print("\n=== Method 1: Simple file object ===")
try:
    with open(file_path, 'rb') as f:
        files = {'fileToUpload': f}
        data = {
            'reqtype': 'fileupload',
            'time': '1h'
        }
        response = requests.post(url, data=data, files=files, timeout=15)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        if response.status_code == 200 and response.text.startswith('http'):
            print("✅ SUCCESS!")
            print(f"URL: {response.text.strip()}")
        else:
            print("❌ FAILED")
except Exception as e:
    print(f"Error: {e}")

# Method 2: With filename (แบบมี tuple)
print("\n=== Method 2: With filename tuple ===")
try:
    with open(file_path, 'rb') as f:
        import os
        filename = os.path.basename(file_path)
        files = {'fileToUpload': (filename, f, 'application/octet-stream')}
        data = {
            'reqtype': 'fileupload',
            'time': '1h'
        }
        response = requests.post(url, data=data, files=files, timeout=15)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        if response.status_code == 200 and response.text.startswith('http'):
            print("✅ SUCCESS!")
            print(f"URL: {response.text.strip()}")
        else:
            print("❌ FAILED")
except Exception as e:
    print(f"Error: {e}")

# Method 3: With browser headers
print("\n=== Method 3: With browser headers ===")
try:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': '*/*',
        'Referer': 'https://litterbox.catbox.moe/'
    }
    with open(file_path, 'rb') as f:
        import os
        filename = os.path.basename(file_path)
        files = {'fileToUpload': (filename, f, 'application/octet-stream')}
        data = {
            'reqtype': 'fileupload',
            'time': '1h'
        }
        response = requests.post(url, data=data, files=files, headers=headers, timeout=15)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        if response.status_code == 200 and response.text.startswith('http'):
            print("✅ SUCCESS!")
            print(f"URL: {response.text.strip()}")
        else:
            print("❌ FAILED")
except Exception as e:
    print(f"Error: {e}")
