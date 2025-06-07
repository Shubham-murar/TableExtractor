import os
from PIL import Image, ImageEnhance, ImageOps

def enhance_table_image(image_path, output_dir="enhanced_images", output_name="enhanced_image.png", sharpness_factor=1.2):
    try:
        img = Image.open(image_path)
        print(f"Successfully opened image: {image_path}")

        grayscale_img = ImageOps.grayscale(img)
        print("Converted image to grayscale.")

        enhancer = ImageEnhance.Sharpness(grayscale_img)
        sharpened_img = enhancer.enhance(sharpness_factor)
        print(f"Applied sharpness enhancement with factor: {sharpness_factor}")

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")

        output_path = os.path.join(output_dir, output_name)
        sharpened_img.save(output_path)
        print(f"Enhanced image saved to: {output_path}")
        return output_path

    except FileNotFoundError:
        print(f"Error: Image not found at {image_path}")
        raise
    except Exception as e:
        print(f"An error occurred during image enhancement: {e}")
        raise

def enhance_multiple_images(image_paths, output_dir="enhanced_images", sharpness_factor=1.2):
    enhanced_paths = []
    for idx, img_path in enumerate(image_paths):
        output_name = f"enhanced_image_{idx+1}.png"
        try:
            output_path = enhance_table_image(
                image_path=img_path,
                output_dir=output_dir,
                output_name=output_name,
                sharpness_factor=sharpness_factor
            )
            enhanced_paths.append(output_path)
        except Exception as e:
            print(f"Skipping image {img_path} due to error: {e}")
    return enhanced_paths

if __name__ == "__main__":
    # Test block
    input_image_path = r'C:\Users\ACER\OneDrive\Desktop\TableMaker\Screenshot 2025-06-02 165116.png'
    output_directory = 'enhanced_images_test_output'
    output_filename = 'sharpened_table_test.png'

    if not os.path.exists(input_image_path):
        print(f"Test image not found at {input_image_path}. Creating dummy image.")
        dummy_img = Image.new('RGB', (200, 100), color='red')
        os.makedirs("test_images_temp", exist_ok=True)
        input_image_path = os.path.join("test_images_temp", "dummy_test_image.png")
        dummy_img.save(input_image_path)

    try:
        enhance_table_image(input_image_path, output_directory, output_filename, sharpness_factor=2.0)
    except Exception as e:
        print(f"Standalone test failed: {e}")
