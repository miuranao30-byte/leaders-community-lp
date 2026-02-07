import os
from PIL import Image
import sys

def optimize_images(directory):
    total_original_size = 0
    total_optimized_size = 0
    
    # Extensions to process
    valid_extensions = {'.png', '.jpg', '.jpeg'}
    
    print(f"Scanning directory: {directory}")
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext not in valid_extensions:
                continue
                
            file_path = os.path.join(root, file)
            original_size = os.path.getsize(file_path)
            total_original_size += original_size
            
            try:
                with Image.open(file_path) as img:
                    # Resize if width > 1920
                    if img.width > 1920:
                        ratio = 1920 / img.width
                        new_height = int(img.height * ratio)
                        img = img.resize((1920, new_height), Image.Resampling.LANCZOS)
                        print(f"Resized {file}: {img.width}x{img.height}")
                    
                    # Compress and Save
                    if ext == '.png':
                        # Check if it has transparency
                        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                            # Save as PNG with optimization
                            img.save(file_path, optimize=True)
                        else:
                            # Convert to JPEG if no transparency (optional, but user said "if possible")
                            # User said: "PNG: if possible jpeg, or optimize=True".
                            # To be safe and keep same file extension as requested "Overwrite with same filename",
                            # I will stick to PNG optimization to avoid breaking links.
                            # Just optimizing PNGs often helps a lot. 
                            # If I change extension, I break HTML links. User said "Overwrite with original filename".
                            # So I MUST keep extension.
                            img.save(file_path, optimize=True)
                            
                    elif ext in {'.jpg', '.jpeg'}:
                        img.save(file_path, quality=80, optimize=True)
                        
                optimized_size = os.path.getsize(file_path)
                total_optimized_size += optimized_size
                print(f"Optimized {file}: {original_size/1024:.1f}KB -> {optimized_size/1024:.1f}KB")
                
            except Exception as e:
                print(f"Error processing {file}: {e}")
                # If optimization fails, keep original count
                total_optimized_size += original_size

    print("-" * 30)
    print(f"Total Original Size: {total_original_size / (1024*1024):.2f} MB")
    print(f"Total Optimized Size: {total_optimized_size / (1024*1024):.2f} MB")
    print(f"Reduction: {total_original_size - total_optimized_size / (1024*1024):.2f} MB ({(1 - total_optimized_size/total_original_size)*100:.1f}%)")

if __name__ == "__main__":
    target_dir = os.path.join(os.getcwd(), "images")
    if len(sys.argv) > 1:
        target_dir = sys.argv[1]
        
    optimize_images(target_dir)
