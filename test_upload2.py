from PIL import Image, ImageDraw
import tempfile
import os
import upload

# Create test image that simulates uploaded photo
img = Image.new('RGB', (800, 600), color='purple')
# Add some content
draw = ImageDraw.Draw(img)

# Save to temp file
with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
    test_path = f.name
    img.save(test_path, 'JPEG')

print(f'Test image created: {test_path}')

# Test upload_tempfile directly  
print('\n--- Testing upload_tempfile directly ---')
result = upload.upload_tempfile(test_path)
if result:
    print(f'✓ TempFile upload success: {result}')
else:
    print('✗ TempFile upload failed')

# Test upload_litterbox
print('\n--- Testing upload_litterbox ---')
result2 = upload.upload_litterbox(test_path)
if result2:
    print(f'✓ Litterbox upload success: {result2}')
else:
    print('✗ Litterbox upload failed')

# Test with cleanup
print('\n--- Testing upload.py execution ---')
import subprocess
proc = subprocess.run(['python', 'upload.py', test_path], capture_output=True, text=True)
print(f'Output: {proc.stdout}')

if proc.returncode == 0:
    try:
        import json
        data = json.loads(proc.stdout)
        print(f'Generated URL: {data.get("url")}')
        print(f'Source: {data.get("source")}')
    except:
        print('Could not parse JSON output')

# Cleanup
if os.path.exists(test_path):
    os.remove(test_path)