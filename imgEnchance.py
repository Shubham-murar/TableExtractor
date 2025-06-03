import os
from PIL import Image, ImageEnhance, ImageOps

def enhance_table_image(image_path, output_dir="enhanced_images", output_name="enhanced_image.png", sharpness_factor=1.2):
    """
    Enhances the quality of an image of a table by converting it to grayscale
    and increasing its sharpness. Saves the enhanced image in a specified directory.

    Args:
        image_path (str): The path to the input image file.
        output_dir (str, optional): The directory to save the enhanced image.
                                      Defaults to "enhanced_images".
        output_name (str, optional): The name of the output image file.
                                      Defaults to "enhanced_image.png".
        sharpness_factor (float, optional): A factor to control the sharpness.
                                           Values > 1 increase sharpness, < 1 decrease.
                                           Defaults to 1.2.
    """
    try:
        # Open the image
        img = Image.open(image_path)
        print(f"Successfully opened image: {image_path}")

        # Convert the image to grayscale
        grayscale_img = ImageOps.grayscale(img)
        print("Converted image to grayscale.")

        # Enhance sharpness
        enhancer = ImageEnhance.Sharpness(grayscale_img)
        sharpened_img = enhancer.enhance(sharpness_factor)
        print(f"Applied sharpness enhancement with factor: {sharpness_factor}")

        # Create the output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")
        
        output_path = os.path.join(output_dir, output_name)

        # Save the enhanced image
        sharpened_img.save(output_path)
        print(f"Enhanced image saved to: {output_path}")

    except FileNotFoundError:
        print(f"Error: Image not found at {image_path}")
        raise # Re-raise the exception to be caught by the caller in main.py
    except Exception as e:
        print(f"An error occurred during image enhancement process: {e}")
        raise # Re-raise the exception

if __name__ == "__main__":
    # Example usage: Replace with your actual image path for testing
    # This part will only run if you execute imgEnchance.py directly
    input_image_path = r'C:\Users\ACER\OneDrive\Desktop\TableMaker\Screenshot 2025-06-02 165116.png' # Example path
    
    # Create a dummy image for testing if the above path doesn't exist
    if not os.path.exists(input_image_path):
        print(f"Test image not found at {input_image_path}. Creating a dummy image for testing.")
        try:
            dummy_img = Image.new('RGB', (200, 100), color = 'red')
            dummy_img_dir = "test_images_temp"
            os.makedirs(dummy_img_dir, exist_ok=True)
            input_image_path = os.path.join(dummy_img_dir, "dummy_test_image.png")
            dummy_img.save(input_image_path)
            print(f"Dummy image saved at {input_image_path}")
        except Exception as e:
            print(f"Could not create dummy image: {e}")
            # Fallback to a non-existent path to test FileNotFoundError if dummy creation fails
            input_image_path = "non_existent_image_for_testing.png"


    output_directory = 'enhanced_images_test_output' # Test output directory
    output_filename = 'sharpened_table_test.png'    # Test output filename
    
    print(f"\n--- Running standalone test for enhance_table_image ---")
    print(f"Input image: {input_image_path}")
    print(f"Output directory: {output_directory}")
    print(f"Output filename: {output_filename}")
    
    try:
        enhance_table_image(input_image_path, output_directory, output_filename, sharpness_factor=2.0)
    except Exception as e:
        print(f"Standalone test failed: {e}")
    print(f"--- End of standalone test ---\n")

