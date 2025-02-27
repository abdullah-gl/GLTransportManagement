import pandas as pd
import dataframe_image as dfi
from datetime import datetime
from django.conf import settings
import logging
import os
import re

logger = logging.getLogger('django')

# Get the current date
current_date = datetime.now().strftime("%Y-%m-%d")

class TransportDataProcessor:
    def __init__(self, data, previous_vedor_name):
        # Define output path and create directory if it doesn't exist
        self.output_media_path = getattr(settings, "MEDIA_ROOT", "media")  # Fallback to 'media' if MEDIA_ROOT is not set
        self.output_media_path = os.path.join(self.output_media_path, "vendor", f"vendor_{current_date}")
        self.previous_vedor_name = previous_vedor_name

        if not os.path.exists(self.output_media_path):
            os.makedirs(self.output_media_path, exist_ok=True)

        self.data = data
        self.generate_table_image()

    def sanitize_filename(self, name):
        """Sanitizes route number to be a valid filename"""
        return re.sub(r'[^\w\-_]', '_', str(name))  # Replace invalid characters with '_'

    def generate_table_image(self):
        vendor_dirs = set()
        for route_no, entries in self.data.items():
            df = pd.DataFrame(entries)
            sanitized_route_no = self.sanitize_filename(route_no)  # Ensure filename is safe
            sanitized_vendor_name = self.sanitize_filename(self.previous_vedor_name)
            vendor_dir = os.path.join(self.output_media_path, sanitized_vendor_name)
            if not os.path.exists(vendor_dir):
                os.makedirs(vendor_dir, exist_ok=True)
                
            vendor_dirs.add(vendor_dir)

            # Apply enhanced styling
            styled_df = df.style.set_properties(**{
                'border': '1px solid #ddd',
                'padding': '10px',
                'font-size': '13pt',
                'text-align': 'left',
                'background-color': '#ffffff',
                'color': '#333'
            }).set_table_styles([
                {'selector': 'thead th', 'props': [
                    ('background-color', '#ff9900'),
                    ('color', 'white'),
                    ('font-weight', 'bold'),
                    ('text-align', 'left'),
                    ('padding', '12px')
                ]},
                {'selector': 'td', 'props': [
                    ('white-space', 'nowrap'),
                    ('overflow', 'hidden'),
                    ('text-overflow', 'ellipsis'),
                    ('padding', '10px')
                ]},
                {'selector': 'tbody tr:nth-child(even)', 'props': [
                    ('background-color', '#f9f9f9')
                ]},
                {'selector': 'tbody tr:hover', 'props': [
                    ('background-color', '#ffcc80')
                ]}
            ])

            # Save the image in the designated output directory
            output_file = os.path.join(vendor_dir, f"{sanitized_vendor_name}_{sanitized_route_no}.png")

            try:
                dfi.export(styled_df, output_file, max_cols=-1, max_rows=-1)
                logger.info(f"Image saved: {output_file}")
            except Exception as e:
                logger.info(f"Error saving image for route {route_no}: {e}")
        
        # logger.info(f"Vendor IMAGE DIRECTORY: {list(vendor_dirs)}")
            
        
        return list(vendor_dirs) 

