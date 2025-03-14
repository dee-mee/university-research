import os
from PIL import Image, ImageDraw
from django.conf import settings
import shutil

def ensure_map_static_dirs():
    """Ensure necessary directories exist for map static files"""
    static_root = getattr(settings, 'STATIC_ROOT', None)
    if not static_root:
        return False
    
    map_img_dir = os.path.join(static_root, 'maps', 'images')
    os.makedirs(map_img_dir, exist_ok=True)
    return map_img_dir

def generate_marker_icons():
    """Generate marker icons for the map"""
    map_img_dir = ensure_map_static_dirs()
    if not map_img_dir:
        print("Static root not configured, can't generate markers")
        return
    
    # Base marker dimensions
    width, height = 25, 41
    
    # Generate active marker (green)
    active_marker = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(active_marker)
    
    # Draw pin shape
    draw.ellipse((0, 0, width, width), fill=(56, 161, 105))  # Green circle
    draw.polygon([
        (width // 2, height),  # Bottom point
        (width // 4, width),   # Bottom left of circle
        (3 * width // 4, width)  # Bottom right of circle
    ], fill=(56, 161, 105))  # Green pin
    
    # Save active marker
    active_marker.save(os.path.join(map_img_dir, 'marker-active.png'))
    
    # Generate inactive marker (gray)
    inactive_marker = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(inactive_marker)
    
    # Draw pin shape
    draw.ellipse((0, 0, width, width), fill=(113, 128, 150))  # Gray circle
    draw.polygon([
        (width // 2, height),  # Bottom point
        (width // 4, width),   # Bottom left of circle
        (3 * width // 4, width)  # Bottom right of circle
    ], fill=(113, 128, 150))  # Gray pin
    
    # Save inactive marker
    inactive_marker.save(os.path.join(map_img_dir, 'marker-inactive.png'))
    
    # Generate shadow
    shadow = Image.new('RGBA', (41, 41), (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow)
    draw.ellipse((0, 0, 41, 41), fill=(0, 0, 0, 128))  # Semi-transparent black
    shadow.save(os.path.join(map_img_dir, 'marker-shadow.png'))
    
    print(f"Marker icons generated in {map_img_dir}")

def copy_leaflet_markers():
    """Alternative: copy default Leaflet markers instead of generating custom ones"""
    map_img_dir = ensure_map_static_dirs()
    if not map_img_dir:
        print("Static root not configured, can't copy markers")
        return
    
    # Define source files if you have them in your project
    # For example, if you have a directory with default leaflet markers
    leaflet_markers_dir = os.path.join(settings.BASE_DIR, 'static', 'leaflet', 'images')
    
    if os.path.exists(leaflet_markers_dir):
        # Copy default markers
        shutil.copy(
            os.path.join(leaflet_markers_dir, 'marker-icon.png'),
            os.path.join(map_img_dir, 'marker-active.png')
        )
        shutil.copy(
            os.path.join(leaflet_markers_dir, 'marker-icon-gray.png'),
            os.path.join(map_img_dir, 'marker-inactive.png')
        )
        shutil.copy(
            os.path.join(leaflet_markers_dir, 'marker-shadow.png'),
            os.path.join(map_img_dir, 'marker-shadow.png')
        )
        print(f"Leaflet markers copied to {map_img_dir}")
    else:
        print("Leaflet markers source directory not found")

if __name__ == "__main__":
    # Run this file directly to generate markers
    generate_marker_icons()