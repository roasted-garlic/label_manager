from app import db
import datetime
import json

class ProductTemplate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    attributes = db.Column(db.Text)  # Stored as JSON
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def set_attributes(self, attrs):
        self.attributes = json.dumps(attrs)

    def get_attributes(self):
        return json.loads(self.attributes) if self.attributes else {}

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    batch_number = db.Column(db.String(8))
    barcode = db.Column(db.String(12), unique=True)  # UPC-A is 12 digits
    attributes = db.Column(db.Text)  # Stored as JSON
    product_image = db.Column(db.String(500))  # URL/path to image
    label_image = db.Column(db.String(500))    # URL/path to image
    template_id = db.Column(db.Integer, db.ForeignKey('product_template.id', ondelete='SET NULL'), nullable=True)
    label_qty = db.Column(db.Integer, default=4, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def set_attributes(self, attrs):
        self.attributes = json.dumps(attrs)

    def get_attributes(self):
        return json.loads(self.attributes) if self.attributes else {}

class GeneratedPDF(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id', ondelete='CASCADE'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    pdf_url = db.Column(db.String(500))
