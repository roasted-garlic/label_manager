
document.addEventListener('DOMContentLoaded', function() {
    // Delete COA handler
    document.querySelectorAll('.delete-coa').forEach(button => {
        button.addEventListener('click', async function() {
            if (confirm('Are you sure you want to delete this COA?')) {
                const productId = this.dataset.productId;
                try {
                    const response = await fetch(`/api/delete_coa/${productId}`, {
                        method: 'DELETE'
                    });
                    if (response.ok) {
                        location.reload();
                    } else {
                        const data = await response.json();
                        alert(data.error || 'Failed to delete COA');
                    }
                } catch (error) {
                    console.error('Error:', error);
                    alert('Error deleting COA');
                }
            }
        });
    });

    const generateBatchBtn = document.getElementById('generateBatch');
    const addAttributeBtn = document.getElementById('addAttribute');
    const attributesContainer = document.getElementById('attributesContainer');
    const templateSelect = document.getElementById('template');

    function initializeDeleteHandler(button) {
        button.addEventListener('click', function() {
            const attributeGroup = button.closest('.attribute-group');
            if (attributeGroup) {
                attributeGroup.remove();
            }
        });
    }

    // Initialize delete handlers for existing attributes
    document.querySelectorAll('.remove-attribute').forEach(button => {
        initializeDeleteHandler(button);
    });

    // Enable/disable batch number editing
    const enableBatchEdit = document.getElementById('enableBatchEdit');
    const batchNumberInput = document.getElementById('batchNumber');
    
    if (enableBatchEdit) {
        enableBatchEdit.addEventListener('change', function() {
            batchNumberInput.readOnly = !this.checked;
            generateBatchBtn.disabled = this.checked;
        });
    }

    // Generate batch number
    if (generateBatchBtn) {
        generateBatchBtn.addEventListener('click', async function() {
            try {
                const response = await fetch('/api/generate_batch', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                if (response.ok) {
                    const data = await response.json();
                    document.getElementById('batchNumber').value = data.batch_number;
                } else {
                    const data = await response.json();
                    alert(data.error || 'Failed to generate batch number');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Error generating batch number');
            }
        });
    }

    // Add attribute fields
    if (addAttributeBtn) {
        addAttributeBtn.addEventListener('click', function() {
            const attributeGroup = document.createElement('div');
            attributeGroup.className = 'attribute-group mb-2';
            
            attributeGroup.innerHTML = `
                <div class="row">
                    <div class="col">
                        <input type="text" class="form-control attr-name" name="attr_name[]" placeholder="Attribute Name" required>
                    </div>
                    <div class="col">
                        <input type="text" class="form-control" name="attr_value[]" placeholder="Attribute Value" required>
                    </div>
                    <div class="col-auto">
                        <button type="button" class="btn btn-danger remove-attribute">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            `;
            
            // Add event listener for lowercase conversion
            const attrNameInput = attributeGroup.querySelector('.attr-name');
            attrNameInput.addEventListener('input', function(e) {
                this.value = this.value.toLowerCase();
            });
            
            attributesContainer.appendChild(attributeGroup);
            
            // Initialize delete handler for the new attribute
            initializeDeleteHandler(attributeGroup.querySelector('.remove-attribute'));
            
            // Focus on the new attribute name input
            attributeGroup.querySelector('.attr-name').focus();
        });
    }

    // Template selection handler
    if (templateSelect) {
        templateSelect.addEventListener('change', async function() {
            const templateId = this.value;
            if (templateId) {
                try {
                    const response = await fetch(`/api/template/${templateId}`);
                    if (!response.ok) {
                        throw new Error('Failed to fetch template');
                    }
                    
                    const template = await response.json();
                    attributesContainer.innerHTML = '';
                    
                    Object.entries(template.attributes).forEach(([name, value]) => {
                        const attributeGroup = document.createElement('div');
                        attributeGroup.className = 'attribute-group mb-2';
                        
                        attributeGroup.innerHTML = `
                            <div class="row">
                                <div class="col">
                                    <input type="text" class="form-control attr-name" name="attr_name[]" value="${name}" required>
                                </div>
                                <div class="col">
                                    <input type="text" class="form-control" name="attr_value[]" value="${value || ''}" required>
                                </div>
                                <div class="col-auto">
                                    <button type="button" class="btn btn-danger remove-attribute">
                                        <i class="fas fa-trash"></i>
                                    </button>
                                </div>
                            </div>
                        `;
                        
                        attributesContainer.appendChild(attributeGroup);
                        initializeDeleteHandler(attributeGroup.querySelector('.remove-attribute'));
                    });
                } catch (error) {
                    console.error('Error loading template:', error);
                    alert('Failed to load template attributes');
                }
            } else {
                // Clear attributes if no template selected
                attributesContainer.innerHTML = '';
            }
        });
    }
});
