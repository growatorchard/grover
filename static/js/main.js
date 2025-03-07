// Main JavaScript file for the Grover app

$(document).ready(function() {
    // Toggle debug mode
    $('#debug-mode-toggle').change(function() {
        $.ajax({
            url: '/toggle_debug',
            method: 'POST',
            success: function(response) {
                console.log('Debug mode:', response.debug_mode);
                // Reload the page to show/hide debug panel
                window.location.reload();
            }
        });
    });

    // Article settings modal handler
    $('#create-article-btn').click(function() {
        $('#articleSettingsModal').modal('show');
    });

    // Load existing articles for the current project
    function loadExistingArticles() {
        $.ajax({
            url: '/articles/list',
            method: 'GET',
            success: function(articles) {
                const container = $('#existing-articles-container');
                
                if (articles.length === 0) {
                    container.html('<div class="alert alert-info">No articles yet.</div>');
                    return;
                }
                
                let html = '<h6 class="mb-3">Existing Articles</h6>';
                
                articles.forEach(art => {
                    html += `
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <div>
                            <strong>${art.article_title || 'Untitled'}</strong> (ID: ${art.id})
                        </div>
                        <div>
                            <button type="button" class="btn btn-sm btn-danger delete-article me-2" data-article-id="${art.id}">
                                <i class="bi bi-trash"></i>
                            </button>
                            <button type="button" class="btn btn-sm btn-primary edit-article" data-article-id="${art.id}">
                                Edit/Generate
                            </button>
                        </div>
                    </div>`;
                });
                
                container.html(html);
            },
            error: function() {
                $('#existing-articles-container').html('<div class="alert alert-danger">Failed to load articles. Please try again.</div>');
            }
        });
    }

    // Load articles if on the main page and a project is selected
    if ($('#existing-articles-container').length > 0) {
        loadExistingArticles();
    }

    // Handle article deletion
    $(document).on('click', '.delete-article', function() {
        if (!confirm('Are you sure you want to delete this article?')) {
            return;
        }
        
        const articleId = $(this).data('article-id');
        
        $.ajax({
            url: '/articles/delete',
            method: 'POST',
            data: { article_id: articleId },
            success: function() {
                loadExistingArticles();
            },
            error: function(xhr) {
                alert('Failed to delete article: ' + xhr.responseText);
            }
        });
    });

    // Handle article editing
    $(document).on('click', '.edit-article', function() {
        const articleId = $(this).data('article-id');
        
        // Redirect to edit page or load article data
        window.location.href = '/articles/select?article_id=' + articleId;
    });

    // Load final article for viewing
    function loadFinalArticle() {
        $.ajax({
            url: '/articles/get_current',
            method: 'GET',
            success: function(article) {
                if (!article) {
                    $('#final-article-container').html('<div class="alert alert-info">No article data available.</div>');
                    return;
                }
                
                let html = `
                
                <div class="mb-3">
                    <label for="final-article-content" class="form-label">Article Content</label>
                    <textarea class="form-control" id="final-article-content" name="article_content" rows="15">${article.article_content || ''}</textarea>
                </div>
                
                <div class="mb-3">
                    <button id="save-final-article-btn" class="btn btn-success ms-2">Save Changes</button>
                </div>`;
                
                $('#final-article-container').html(html);
            },
            error: function() {
                $('#final-article-container').html('<div class="alert alert-danger">Failed to load article data.</div>');
            }
        });
    }

    // Load final article if on the main page and article_id is set
    if ($('#final-article-container').length > 0) {
        loadFinalArticle();
    }

    // Save final article
    $(document).on('click', '#save-final-article-btn', function() {
        const btn = $(this);
        const articleTitle = $('#final-article-title').val().trim();
        const articleContent = $('#final-article-content').val().trim();
        const metaTitle = $('#final-meta-title').val().trim();
        const metaDesc = $('#final-meta-desc').val().trim();
        
        btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Saving...');
        
        $.ajax({
            url: '/articles/save',
            method: 'POST',
            data: {
                article_title: articleTitle,
                article_content: articleContent,
                meta_title: metaTitle,
                meta_description: metaDesc
            },
            success: function(response) {
                btn.prop('disabled', false).text('Save Changes');
                
                if (response.error) {
                    alert('Error: ' + response.error);
                    return;
                }
                
                // Show success message
                $('<div class="alert alert-success alert-dismissible fade show" role="alert">')
                    .text('Article saved successfully.')
                    .append('<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>')
                    .prependTo('#final-article-container');
            },
            error: function(xhr) {
                btn.prop('disabled', false).text('Save Changes');
                alert('Failed to save article: ' + xhr.responseText);
            }
        });
    });

    // View article content
    function loadViewArticle() {
        $.ajax({
            url: '/articles/get_current',
            method: 'GET',
            success: function(article) {
                if (!article) {
                    $('#preview-article-container').html('<div class="alert alert-info">No article data available.</div>');
                    return;
                }
                
                let html = `
                <div class="mb-3">
                    <h5>Title</h5>
                    <p class="border p-2 bg-light">${article.article_title || 'Untitled'}</p>
                </div>
                
                <div class="mb-3">
                    <h5>Article Content</h5>
                    <div class="border p-3 bg-light markdown-content">
                        ${renderMarkdown(article.article_content || 'No content available')}
                    </div>
                </div>
                
                <div class="mb-3">
                    <button id="copy-markdown-btn" class="btn btn-primary">Copy Raw Markdown</button>
                </div>`;
                
                $('#preview-article-container').html(html);
            },
            error: function() {
                $('#preview-article-container').html('<div class="alert alert-danger">Failed to load article data.</div>');
            }
        });
    }

    // Simple function to render markdown (in a real app, you'd use a proper markdown library)
    function renderMarkdown(text) {
        // This is a very basic implementation - use a library like marked.js for production
        let html = text
            .replace(/^# (.*$)/gm, '<h1>$1</h1>')
            .replace(/^## (.*$)/gm, '<h2>$1</h2>')
            .replace(/^### (.*$)/gm, '<h3>$1</h3>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n/g, '<br>');
        
        return html;
    }

    // Load view article if on the main page
    if ($('#preview-article-container').length > 0) {
        loadViewArticle();
    }

    // Copy raw markdown
    $(document).on('click', '#copy-markdown-btn', function() {
        $.ajax({
            url: '/articles/get_current',
            method: 'GET',
            success: function(article) {
                if (!article || !article.article_content) {
                    alert('No article content available to copy.');
                    return;
                }
                
                // Create a temporary textarea element to copy the text
                const textarea = document.createElement('textarea');
                textarea.value = article.article_content;
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand('copy');
                document.body.removeChild(textarea);
                
                alert('Article content copied to clipboard!');
            },
            error: function() {
                alert('Failed to copy article content.');
            }
        });
    });

    // Load community revision interface
    function loadCommunityRevision() {
        $.ajax({
            url: '/communities/list',
            method: 'GET',
            success: function(communities) {
                let html = `
                <div class="mb-3">
                    <label for="community-select" class="form-label">Select Community for Revision</label>
                    <select class="form-select" id="community-select">
                        <option value="">None</option>`;
                
                communities.forEach(community => {
                    html += `<option value="${community.id}">${community.community_name} (ID: ${community.id})</option>`;
                });
                
                html += `
                    </select>
                </div>
                
                <div id="community-details" class="mb-3" style="display: none;">
                    <!-- Community details will be loaded here -->
                </div>
                
                <div class="mb-3">
                    <button id="generate-community-revision-btn" class="btn btn-primary" disabled>Generate Community Revision</button>
                </div>
                
                <div id="revision-results" class="mt-3" style="display: none;">
                    <!-- Revision results will be shown here -->
                </div>`;
                
                $('#community-revision-container').html(html);
            },
            error: function() {
                $('#community-revision-container').html('<div class="alert alert-danger">Failed to load communities.</div>');
            }
        });
    }

    // Load community revision if on the main page
    if ($('#community-revision-container').length > 0) {
        loadCommunityRevision();
    }

    // Handle community selection
    $(document).on('change', '#community-select', function() {
        const communityId = $(this).val();
        const generateBtn = $('#generate-community-revision-btn');
        
        if (!communityId) {
            $('#community-details').hide();
            generateBtn.prop('disabled', true);
            return;
        }
        
        // Load community details
        $.ajax({
            url: `/communities/${communityId}`,
            method: 'GET',
            success: function(data) {
                const community = data.community;
                
                let html = `
                <div class="card">
                    <div class="card-header">
                        <h6 class="mb-0">Community Details</h6>
                    </div>
                    <div class="card-body">
                        <p><strong>Name:</strong> ${community.community_name}</p>
                        <p><strong>Location:</strong> ${community.city}, ${community.state}</p>
                        <p><strong>Primary Domain:</strong> ${community.community_primary_domain}</p>
                        <p><strong>Aliases:</strong> ${data.aliases.map(a => a.alias).join(', ') || 'None'}</p>
                        <p><strong>Available Care Areas:</strong><p/>
                        ${data.care_area_details}
                    </div>
                </div>`;
                
                $('#community-details').html(html).show();
                generateBtn.prop('disabled', false);
            },
            error: function() {
                $('#community-details').html('<div class="alert alert-danger">Failed to load community details.</div>').show();
                generateBtn.prop('disabled', true);
            }
        });
    });

    // Generate community revision
    $(document).on('click', '#generate-community-revision-btn', function() {
        const btn = $(this);
        const communityId = $('#community-select').val();
        
        if (!communityId) {
            alert('Please select a community first.');
            return;
        }
        
        btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Generating...');
        
        $.ajax({
            url: '/articles/community_revision',
            method: 'POST',
            data: {
                community_id: communityId
            },
            success: function(response) {
                btn.prop('disabled', false).text('Generate Community Revision');
                
                if (response.error) {
                    alert('Error: ' + response.error);
                    return;
                }
                
                // Display results
                let html = `
                <div class="alert alert-success">
                    Community revision saved as new article (ID: ${response.article_id}).
                </div>
                
                <div class="card">
                    <div class="card-header">
                        <h6 class="mb-0">Revised Article</h6>
                    </div>
                    <div class="card-body">
                        <div class="border p-3 bg-light markdown-content">
                            ${renderMarkdown(response.revised_text)}
                        </div>
                    </div>
                </div>
                
                <div class="mt-3">
                    <a href="/" class="btn btn-primary">View in Article Editor</a>
                </div>`;
                
                $('#revision-results').html(html).show();
                
                // Display token usage
                // const costs = response.costs;
                // $('#revision-token-usage-info').html(`
                //     <strong>Token Usage & Costs:</strong><br>
                //     - Input: ${costs.prompt_tokens.toLocaleString()} tokens ($${costs.input_cost.toFixed(4)})<br>
                //     - Output: ${costs.completion_tokens.toLocaleString()} tokens ($${costs.output_cost.toFixed(4)})<br>
                //     - Total: ${costs.total_tokens.toLocaleString()} tokens ($${costs.total_cost.toFixed(4)})
                // `);
            },
            error: function(xhr) {
                btn.prop('disabled', false).text('Generate Community Revision');
                alert('Failed to generate community revision: ' + xhr.responseText);
            }
        });
    });

    // Auto-save functionality for fields in the final article section
    let autoSaveTimeout;
    $(document).on('input', '#final-article-title, #final-article-content, #final-meta-title, #final-meta-desc', function() {
        clearTimeout(autoSaveTimeout);
        autoSaveTimeout = setTimeout(function() {
            $('#save-final-article-btn').click();
        }, 3000); // Auto-save after 3 seconds of inactivity
    });
});