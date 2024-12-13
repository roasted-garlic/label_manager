import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy.orm import DeclarativeBase
import logging
from werkzeug.utils import secure_filename
import string
import random
import requests
from PIL import Image
import io
import base64

import utils

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
app = Flask(__name__)

# Configuration
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or "a secret key"
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

db.init_app(app)
migrate = Migrate(app, db)

logging.basicConfig(level=logging.DEBUG)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

with app.app_context():
    import models
    db.create_all()

@app.route('/')
def index():
    products = models.Product.query.all()
    return render_template('product_list.html', products=products)

def fetch_craftmypdf_templates():
    """Fetch templates from CraftMyPDF API"""
    api_key = os.environ.get('CRAFTMYPDF_API_KEY')
    if not api_key:
        app.logger.error("CraftMyPDF API key not configured")
        return []
    
    headers = {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json'
    }
    
    try:
        app.logger.debug("Fetching templates from CraftMyPDF API")
        app.logger.debug(f"Using API endpoint: https://api.craftmypdf.com/v1/list-templates")
        
        response = requests.get(
            'https://api.craftmypdf.com/v1/list-templates',
            headers=headers,
            params={'limit': 300, 'offset': 0},
            timeout=30
        )
        
        app.logger.debug(f"API Response Status: {response.status_code}")
        app.logger.debug(f"API Response Headers: {response.headers}")
        app.logger.debug(f"API Response Content: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            templates = data.get('templates', [])
            app.logger.info(f"Successfully fetched {len(templates)} templates")
            
            # Log template IDs for debugging
            for template in templates:
                app.logger.debug(f"Template ID: {template.get('template_id')}, Name: {template.get('name')}")
            
            return templates
        else:
            app.logger.error(f"Failed to fetch templates. Status: {response.status_code}, Response: {response.text}")
            return []
            
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Request error fetching templates: {str(e)}")
        return []
    except Exception as e:
        app.logger.error(f"Unexpected error fetching templates: {str(e)}")
        return []

@app.route('/product/new', methods=['GET', 'POST'])
def create_product():
    templates = models.ProductTemplate.query.all()
    pdf_templates = fetch_craftmypdf_templates()
    
    if request.method == 'POST':
        name = request.form.get('name')  # Changed from title to name
        attributes = {}
        
        # Process dynamic attributes
        attr_names = request.form.getlist('attr_name[]')
        attr_values = request.form.getlist('attr_value[]')
        attributes = dict(zip(attr_names, attr_values))

        # Handle file uploads
        product_image = request.files.get('product_image')
        label_image = request.files.get('label_image')

        # Generate UPC-A barcode number
        barcode_number = utils.generate_upc_barcode()

        product = models.Product(
            name=name,
            batch_number=utils.generate_batch_number(),
            sku=utils.generate_sku(),  # Use dedicated SKU generator
            barcode=barcode_number,
            craftmypdf_template_id=request.form.get('craftmypdf_template_id')
        )
        product.set_attributes(attributes)

        if product_image:
            product.product_image = save_image(product_image)
        if label_image:
            product.label_image = save_image(label_image)

        db.session.add(product)
        db.session.commit()
        
        flash('Product created successfully!', 'success')
        return redirect(url_for('product_detail', product_id=product.id))

    return render_template('product_create.html', templates=templates, pdf_templates=pdf_templates)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = models.Product.query.get_or_404(product_id)
    pdfs = models.GeneratedPDF.query.filter_by(product_id=product_id).all()
    return render_template('product_detail.html', product=product, pdfs=pdfs)

@app.route('/api/generate_batch', methods=['POST'])
def generate_batch():
    return jsonify({'batch_number': generate_batch_number()})

@app.route('/api/generate_pdf/<int:product_id>', methods=['POST'])
def generate_pdf(product_id):
    try:
        product = models.Product.query.get_or_404(product_id)
        
        # Get API key from environment
        api_key = os.environ.get('CRAFTMYPDF_API_KEY')
        if not api_key:
            app.logger.error("API key not configured")
            return jsonify({'error': 'API key not configured'}), 500

        # Get the label data in the correct format
        json_response = generate_json(product_id)
        if isinstance(json_response, tuple):  # Error case
            return json_response
            
        # Get the JSON data for the product
        json_data = json_response.json
        
        # Structure API request data
        api_data = {
            "template_id": product.craftmypdf_template_id,
            "export_type": "pdf",
            "cloud_storage": 1,
            "data": [json_data] if product.label_qty == 1 else json_data["label_data"]
        }
        
        app.logger.debug(f"Sending request to CraftMyPDF API with payload: {api_data}")
        
        # Make API call
        headers = {
            'X-API-KEY': api_key,
            'Content-Type': 'application/json'
        }
        
        # Make API request with detailed logging
        response = requests.post(
            'https://api.craftmypdf.com/v1/create',
            json=api_data,
            headers=headers,
            timeout=30
        )
        
        # Log full request and response details for debugging
        app.logger.debug(f"CraftMyPDF API Request URL: https://api.craftmypdf.com/v1/create")
        app.logger.debug(f"CraftMyPDF API Headers: {headers}")
        app.logger.debug(f"CraftMyPDF API Response Status: {response.status_code}")
        app.logger.debug(f"CraftMyPDF API Response Content: {response.text}")
        
        if response.status_code != 200:
            error_msg = f"API Error (Status {response.status_code}): {response.text}"
            app.logger.error(error_msg)
            return jsonify({'error': error_msg}), response.status_code
        
        result = response.json()
        if not result.get('success'):
            error_msg = result.get('message', 'Unknown error')
            app.logger.error(f"API Error: {error_msg}")
            return jsonify({'error': error_msg}), 400
            
        pdf_url = result.get('file_url')
        if not pdf_url:
            app.logger.error("No PDF URL in response")
            return jsonify({'error': 'No PDF URL in response'}), 500
            
        # Create PDF record
        pdf = models.GeneratedPDF(
            product_id=product.id,
            filename=f"{product.name}_{product.batch_number}.pdf",
            pdf_url=pdf_url
        )
        db.session.add(pdf)
        db.session.commit()
        
        return jsonify({'success': True, 'pdf_url': pdf_url})
        
    except requests.exceptions.RequestException as e:
        app.logger.error(f"API request error: {str(e)}")
        return jsonify({'error': str(e)}), 500
    except Exception as e:
        app.logger.error(f"PDF generation error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete_pdf/<int:pdf_id>', methods=['DELETE'])
def delete_pdf(pdf_id):
    pdf = models.GeneratedPDF.query.get_or_404(pdf_id)
    db.session.delete(pdf)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/template/<int:template_id>')
def get_template(template_id):
    template = models.ProductTemplate.query.get_or_404(template_id)
    return jsonify({
        'id': template.id,
        'name': template.name,
        'attributes': template.get_attributes()
    })

@app.route('/templates')
def template_list():
    templates = models.ProductTemplate.query.all()
    return render_template('template_list.html', templates=templates)

@app.route('/template/new', methods=['GET', 'POST'])
def create_template():
    if request.method == 'POST':
        try:
            template = models.ProductTemplate(
                name=request.form['name']
            )
            
            # Handle attributes
            attributes = {}
            attr_names = request.form.getlist('attr_name[]')
            for name in attr_names:
                if name:  # Only add if name is provided
                    attributes[name] = ""  # Empty value as it's just a template
            template.set_attributes(attributes)
            
            db.session.add(template)
            db.session.commit()
            
            flash('Template created successfully!', 'success')
            return redirect(url_for('template_list'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating template: {str(e)}', 'danger')
            return render_template('template_create.html')
    
    return render_template('template_create.html')

@app.route('/template/<int:template_id>/edit', methods=['GET', 'POST'])
def edit_template(template_id):
    template = models.ProductTemplate.query.get_or_404(template_id)
    
    if request.method == 'POST':
        try:
            template.name = request.form['name']
            
            # Handle attributes
            attributes = {}
            attr_names = request.form.getlist('attr_name[]')
            for name in attr_names:
                if name:  # Only add if name is provided
                    attributes[name] = ""  # Empty value as it's just a template
            template.set_attributes(attributes)
            
            db.session.commit()
            flash('Template updated successfully!', 'success')
            return redirect(url_for('template_list'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating template: {str(e)}', 'danger')
            return render_template('template_edit.html', template=template)
    
    return render_template('template_edit.html', template=template)

@app.route('/api/delete_template/<int:template_id>', methods=['DELETE'])
def delete_template(template_id):
    try:
        template = models.ProductTemplate.query.get_or_404(template_id)
        db.session.delete(template)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/product/<int:product_id>/edit', methods=['GET', 'POST'])
def edit_product(product_id):
    product = models.Product.query.get_or_404(product_id)
    
    if request.method == 'POST':
        try:
            product.name = request.form['name']
            product.batch_number = request.form['batch_number']
            
            # Handle attributes
            attributes = {}
            attr_names = request.form.getlist('attr_name[]')
            attr_values = request.form.getlist('attr_value[]')
            for name, value in zip(attr_names, attr_values):
                if name and value:  # Only add if both name and value are provided
                    attributes[name] = value
            product.set_attributes(attributes)
            
            # Generate and save barcode
            barcode_number = utils.generate_upc_barcode()
            
            # Handle product image
            if 'product_image' in request.files and request.files['product_image'].filename:
                file = request.files['product_image']
                if file and utils.is_valid_image(file):
                    if product.product_image:  # Delete old image if it exists
                        try:
                            os.remove(os.path.join('static', product.product_image))
                        except OSError:
                            pass
                    filename = utils.clean_filename(file.filename)
                    filepath = os.path.join('uploads', filename)
                    processed_image = utils.process_image(file)
                    with open(os.path.join('static', filepath), 'wb') as f:
                        f.write(processed_image.getvalue())
                    product.product_image = filepath
            
            # Handle label image
            if 'label_image' in request.files and request.files['label_image'].filename:
                file = request.files['label_image']
                if file and utils.is_valid_image(file):
                    if product.label_image:  # Delete old image if it exists
                        try:
                            os.remove(os.path.join('static', product.label_image))
                        except OSError:
                            pass
                    filename = utils.clean_filename(file.filename)
                    filepath = os.path.join('uploads', filename)
                    processed_image = utils.process_image(file)
                    with open(os.path.join('static', filepath), 'wb') as f:
                        f.write(processed_image.getvalue())
                    product.label_image = filepath
            
            db.session.commit()
            flash('Product updated successfully!', 'success')
            return redirect(url_for('product_detail', product_id=product.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating product: {str(e)}', 'danger')
            return render_template('product_edit.html', product=product)
    
    return render_template('product_edit.html', product=product)

@app.route('/api/delete_product/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    try:
        product = models.Product.query.get_or_404(product_id)
        
        # Delete the product images if they exist
        if product.product_image:
            try:
                image_path = os.path.join('static', product.product_image)
                if os.path.exists(image_path):
                    os.remove(image_path)
            except OSError as e:
                logging.error(f"Error deleting product image: {e}")
                
        if product.label_image:
            try:
                image_path = os.path.join('static', product.label_image)
                if os.path.exists(image_path):
                    os.remove(image_path)
            except OSError as e:
                logging.error(f"Error deleting label image: {e}")
        
        db.session.delete(product)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting product: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate_json/<int:product_id>')
def generate_json(product_id):
    try:
        product = models.Product.query.get_or_404(product_id)
        app.logger.debug(f"Generating JSON for product ID: {product_id}")
        
        # Get product data with all fields
        product_data = product.to_json_data()
        
        # If label image exists, convert to full URL
        if product.label_image:
            product_data["background"] = url_for('static', filename=product.label_image, _external=True)
        
        # Create the specified number of labels
        label_data = [product_data.copy() for _ in range(product.label_qty)]
        
        app.logger.debug(f"Generated JSON data: {label_data}")
        
        # Return single object for single label, array for multiple
        if product.label_qty == 1:
            return jsonify(label_data[0])
        else:
            return jsonify({"label_data": label_data})
        
    except Exception as e:
        app.logger.error(f"Error generating JSON: {str(e)}")
        return jsonify({'error': str(e)}), 500


def generate_batch_number():
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(8))

def save_image(file):
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    # Process and save image
    img = Image.open(file)
    img.thumbnail((800, 800))  # Resize if needed
    img.save(filepath)
    
    # Return relative path from static folder
    return filepath.replace('static/', '', 1)