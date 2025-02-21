import os
import json
import pandas as pd
import numpy as np
import dataframe_image as dfi
from datetime import time
from django.conf import settings

class TransportDataProcessor:
    def __init__(self, file_path):
        output_media_path = os.path.join(settings.MEDIA_ROOT, "vendor")
        self.file_path = file_path
        self.output_dir = output_media_path
        self.route_dict = {}

    def read_excel_file(self):
        """Read the Excel file and clean up headers."""
        df = pd.read_csv(self.file_path, header=None)
        df.columns = df.iloc[0]
        df = df[1:]
        df = df[df[df.columns[0]] != df.columns[0]]
        df.reset_index(drop=True, inplace=True)
        return df

    @staticmethod
    def convert_values(data):
        """Convert non-serializable values in a dictionary."""
        converted_data = {}
        for key, value in data.items():
            if isinstance(value, time):
                converted_data[key] = value.strftime("%H:%M:%S")
            elif isinstance(value, pd.Timestamp):
                converted_data[key] = value.strftime("%Y-%m-%d %H:%M:%S") if not pd.isna(value) else None
            elif pd.isna(value):
                converted_data[key] = None
            elif isinstance(value, np.float64):
                converted_data[key] = float(value)
            else:
                converted_data[key] = value
        return converted_data

    def categorize_data(self, df):
        """Categorize data into a nested dictionary by 'Vendor Name' and 'Route No'."""
        for _, row in df.iterrows():
            vendor, route_no = row["Vendor Name"], row["Route No"]
            if vendor not in self.route_dict:
                self.route_dict[vendor] = {}
            if route_no not in self.route_dict[vendor]:
                self.route_dict[vendor][route_no] = []
            self.route_dict[vendor][route_no].append(self.convert_values(row.to_dict()))

    @staticmethod
    def save_df_as_image(df, path):
        """Save DataFrame as an image with styling."""
        df = df.set_index("S No")
        styles = [
            {'selector': 'thead th', 'props': [('background-color', '#ff9900'), ('color', 'black'), ('font-weight', 'bold'), ('text-align', 'left')]},
            {'selector': 'td', 'props': [('white-space', 'nowrap'), ('overflow', 'hidden'), ('text-overflow', 'ellipsis')]}
        ]
        styled_df = df.style.set_table_styles(styles)
        dfi.export(styled_df, path)

    def save_images(self):
        """Save each route's data as an image."""
        os.makedirs(self.output_dir, exist_ok=True)
        for vendor, routes in self.route_dict.items():
            for route, users in routes.items():
                df_users = pd.DataFrame(users)
                df_users = df_users[['S No', 'Route No','Name','SUV','Shift','Vendor Name',   'Area','Location-Delhi'    ,'Pickup Time','Address (Office Reporting Time 07:20 Hrs & Departure Time 16:45 Hrs)','Vendor Email','Gender']]
                filename = f"{vendor}_{route}.png".replace(" ", "_").replace("/", "-")
                save_path = os.path.join(self.output_dir, filename)
                try:
                    self.save_df_as_image(df_users, save_path)
                    print(f"✅ Saved: {save_path}")
                except Exception as e:
                    print(f"❌ Error saving {save_path}: {e}")

    def save_json(self):
        """Save the categorized data as a JSON file."""
        with open("route_data.json", "w") as f:
            json.dump(self.route_dict, f, indent=4)
        print("JSON saved successfully.")

    def process(self):
        """Execute the full data processing pipeline."""
        df = self.read_excel_file()
        self.categorize_data(df)
        self.save_images()
        return self.route_dict
        # self.save_json()

