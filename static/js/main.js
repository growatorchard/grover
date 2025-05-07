// Main JavaScript file for the Grover app

// Define these functions in the global scope
window.loadFinalArticle = null;
window.loadViewArticle = null;
window.initializeArticleHandlers = null;
window.renderMarkdown = null;

$(document).ready(function () {
    // Toggle debug mode
    $('#debug-mode-toggle').change(function () {
        $.ajax({
            url: '/toggle_debug',
            method: 'POST',
            success: function (response) {
                console.log('Debug mode:', response.debug_mode);
                // Reload the page to show/hide debug panel
                window.location.reload();
            }
        });
    });

    // Article settings modal handler
    $('#create-article-btn').click(function () {
        $('#articleSettingsModal').modal('show');
    });

    // Load existing articles for the current project
    function loadExistingArticles() {
        $.ajax({
            url: '/articles/list',
            method: 'GET',
            success: function (articles) {
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
            error: function () {
                $('#existing-articles-container').html('<div class="alert alert-danger">Failed to load articles. Please try again.</div>');
            }
        });
    }

    // Load articles if on the main page and a project is selected
    if ($('#existing-articles-container').length > 0) {
        loadExistingArticles();
    }

    // Handle article deletion
    $(document).on('click', '.delete-article', function () {
        if (!confirm('Are you sure you want to delete this article?')) {
            return;
        }

        const articleId = $(this).data('article-id');

        $.ajax({
            url: '/articles/delete',
            method: 'POST',
            data: { article_id: articleId },
            success: function () {
                loadExistingArticles();
            },
            error: function (xhr) {
                alert('Failed to delete article: ' + xhr.responseText);
            }
        });
    });

    // Handle article editing
    $(document).on('click', '.edit-article', function () {
        const articleId = $(this).data('article-id');

        // Redirect to edit page or load article data
        window.location.href = '/articles/select?article_id=' + articleId;
    });

    // Load final article for viewing
    window.loadFinalArticle = function() {
        $.ajax({
            url: '/articles/get_current',
            method: 'GET',
            success: function (article) {
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
                
                // Initialize any necessary event handlers or plugins
                window.initializeArticleHandlers();
            },
            error: function () {
                $('#final-article-container').html('<div class="alert alert-danger">Failed to load article data.</div>');
            }
        });
    };
    loadFinalArticle = window.loadFinalArticle;

    // Initialize article-related event handlers
    window.initializeArticleHandlers = function() {
        // Save final article
        $(document).off('click', '#save-final-article-btn').on('click', '#save-final-article-btn', function () {
            const btn = $(this);
            const articleContent = $('#final-article-content').val().trim();

            btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Saving...');

            $.ajax({
                url: '/articles/save_article_post_content',
                method: 'POST',
                data: {
                    article_content: articleContent,
                },
                success: function (response) {
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
                    
                    // Reload the article content to ensure it's up to date
                    loadFinalArticle();
                    
                    // Also update the preview if it exists
                    if ($('#preview-article-container').length > 0) {
                        loadViewArticle();
                    }
                },
                error: function (xhr) {
                    btn.prop('disabled', false).text('Save Changes');
                    alert('Failed to save article: ' + xhr.responseText);
                }
            });
        });
    };

    // View article content
    window.loadViewArticle = function() {
        $.ajax({
            url: '/articles/get_current',
            method: 'GET',
            success: function (article) {
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
                        ${window.renderMarkdown(article.article_content || 'No content available')}
                    </div>
                </div>
                
                <div class="mb-3">
                    <button id="copy-markdown-btn" class="btn btn-primary">Copy Raw Markdown</button>
                </div>`;

                $('#preview-article-container').html(html);
                
                // Initialize copy button handler
                initializeCopyButton();
            },
            error: function () {
                $('#preview-article-container').html('<div class="alert alert-danger">Failed to load article data.</div>');
            }
        });
    };
    loadViewArticle = window.loadViewArticle;

    // Enhanced markdown rendering function
    window.renderMarkdown = function(text) {
        if (!text) return '';
        
        // Convert markdown to HTML using marked.js with security options
        return DOMPurify.sanitize(marked.parse(text, {
            breaks: true,
            gfm: true,
            headerIds: true,
            mangle: false
        }));
    };
    renderMarkdown = window.renderMarkdown;

    // Initialize copy button handler
    function initializeCopyButton() {
        $(document).off('click', '#copy-markdown-btn').on('click', '#copy-markdown-btn', function () {
            $.ajax({
                url: '/articles/get_current',
                method: 'GET',
                success: function (article) {
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

                    // Show feedback
                    const btn = $('#copy-markdown-btn');
                    const originalText = btn.text();
                    btn.text('Copied!');
                    setTimeout(() => {
                        btn.text(originalText);
                    }, 2000);
                },
                error: function () {
                    alert('Failed to copy article content.');
                }
            });
        });
    }

    // Load articles on page load
    $(document).ready(function() {
        console.log("Document ready - loading article sections");
        // Load final article if container exists
        if ($('#final-article-container').length > 0) {
            console.log("Loading final article");
            window.loadFinalArticle();
        }
        
        // Load preview article if container exists
        if ($('#preview-article-container').length > 0) {
            console.log("Loading preview article");
            window.loadViewArticle();
        }
    });
    
    // Ensure articles are loaded when tabs are shown
    $(document).on('shown.bs.collapse', '#finalArticleSection', function () {
        console.log("Final article section opened - loading content");
        window.loadFinalArticle();
    });
    
    $(document).on('shown.bs.collapse', '#viewArticleSection', function () {
        console.log("Preview article section opened - loading content");
        window.loadViewArticle();
    });

    // Community article related functions
    $(document).ready(function () {
        // Load existing community articles
        function loadCommunityArticles() {
            const baseArticleId = $('#article-select').val();
            if (!baseArticleId || baseArticleId === 'new') {
                return;
            }

            $.ajax({
                url: '/community_articles/list',
                method: 'GET',
                data: { base_article_id: baseArticleId },
                success: function (articles) {
                    const container = $('#community-articles-list');

                    if (!container.length) {
                        return;
                    }

                    if (articles.length === 0) {
                        container.html('<div class="alert alert-info">No community articles yet.</div>');
                        return;
                    }

                    let html = '<h6 class="mb-3">Existing Community Articles</h6>';

                    articles.forEach(art => {
                        html += `
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <div>
                            <strong>${art.community_name || 'Untitled'}</strong> (ID: ${art.id})
                        </div>
                        <div>
                            <button type="button" class="btn btn-sm btn-danger delete-community-article me-2" data-article-id="${art.id}">
                                <i class="bi bi-trash"></i>
                            </button>
                            <button type="button" class="btn btn-sm btn-primary edit-community-article" data-article-id="${art.id}">
                                Edit
                            </button>
                        </div>
                    </div>`;
                    });

                    container.html(html);
                },
                error: function (error) {
                    console.error('Error loading community articles:', error);
                    if ($('#community-articles-list').length) {
                        $('#community-articles-list').html('<div class="alert alert-danger">Failed to load community articles. Please try again.</div>');
                    }
                }
            });
        }

        // Load initial community articles if we're on the community article page
        if ($('#community-articles-list').length > 0) {
            loadCommunityArticles();
        }

        // Load communities for the community article form
        if ($('#community-select').length > 0) {
            $.ajax({
                url: '/communities/list',
                method: 'GET',
                success: function (communities) {
                    const select = $('#community-select');
                    console.log('Communities:', communities);

                    if (communities.length === 0) {
                        select.html('<option value="">No communities available</option>');
                        return;
                    }

                    select.find('option:not(:first)').remove();

                    communities.forEach(function (community) {
                        select.append(`<option value="${community.id}">${community.community_name} (ID: ${community.id})</option>`);
                    });
                },
                error: function (error) {
                    console.error('Error loading communities:', error);
                    $('#community-select').html('<option value="">Error loading communities</option>');
                }
            });
        }

        $(document).on('change', '#community-select', function () {
            const communityId = $(this).val();
            console.log('Selected community:', communityId);
            const createBtn = $('#create-community-article-btn');

            // Reset UI elements
            $('#community-details').hide();
            $('#care-area-warning').hide().empty();
            createBtn.prop('disabled', true);

            if (!communityId) {
                return;
            }

            // Show loading indicator
            $('#community-details').html(`
        <div class="text-center py-3">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <p class="mt-2">Loading community details...</p>
        </div>
    `).show();

            // Load community details
            $.ajax({
                url: `/communities/${communityId}`,
                method: 'GET',
                success: function (data) {
                    console.log("Community data received:", data);

                    const community = data.community;
                    createBtn.prop('disabled', false);
                    // Create community details card
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
                    <div class="mt-3">
                        <h6>Care Area Details:</h6>
                        <div class="care-area-details mt-2">
                            ${data.care_area_details}
                        </div>
                    </div>
                </div>
            </div>`;

                    $('#community-details').html(html).show();
                },
                error: function (error) {
                    console.error('Error loading community details:', error);

                    $('#community-details').html(`
                <div class="alert alert-danger">
                    <strong>Error:</strong> Failed to load community details. Please try again.
                </div>
            `).show();
                    createBtn.prop('disabled', true);
                }
            });
        });

        // Create community article
        $(document).on('click', '#create-community-article-btn', function () {
            const btn = $(this);
            const communityId = $('#community-select').val();

            if (!communityId) {
                alert('Please select a community first.');
                return;
            }

            btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Creating...');

            $.ajax({
                url: '/community_articles/create',
                method: 'POST',
                data: {
                    community_id: communityId
                },
                success: function (response) {
                    if (response.error) {
                        alert('Error: ' + response.error);
                        btn.prop('disabled', false).text('Create Community Article');
                        return;
                    }

                    // Redirect to refresh the page with the new community article selected
                    window.location.href = '/';
                },
                error: function (xhr) {
                    alert('Failed to create community article: ' + xhr.responseText);
                    btn.prop('disabled', false).text('Create Community Article');
                }
            });
        });

        // Handle community article deletion
        $(document).on('click', '.delete-community-article', function () {
            if (!confirm('Are you sure you want to delete this community article?')) {
                return;
            }

            const articleId = $(this).data('article-id');

            $.ajax({
                url: '/community_articles/delete',
                method: 'POST',
                data: { community_article_id: articleId },
                success: function () {
                    loadCommunityArticles();
                },
                error: function (xhr) {
                    alert('Failed to delete community article: ' + xhr.responseText);
                }
            });
        });

        // Handle community article editing
        $(document).on('click', '.edit-community-article', function () {
            const articleId = $(this).data('article-id');

            // Post to select_community_article
            $.ajax({
                url: '/community_articles/select',
                method: 'POST',
                data: { community_article_id: articleId },
                success: function () {
                    // Reload the page
                    window.location.reload();
                },
                error: function (xhr) {
                    alert('Failed to select community article: ' + xhr.responseText);
                }
            });
        });

        // Generate community-specific content
        $(document).on('click', '#generate-community-content-btn', function () {
            const btn = $(this);
            btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Generating...');

            $.ajax({
                url: '/articles/community_revision',
                method: 'POST',
                data: {
                    community_id: $('#generate-community-content-btn').data('community-id')
                },
                success: function (response) {
                    btn.prop('disabled', false).text('Generate Community-Specific Content');

                    if (response.error) {
                        $('#community-generation-error')
                            .html(`<div class="alert alert-danger">
                            <strong>Error:</strong> ${response.error}
                        </div>`)
                            .show();
                        return;
                    }

                    // Hide any previous errors
                    $('#community-generation-error').hide();

                    // Update the content fields
                    $('#community-article-content').val(response.article_content);

                    // Show success message
                    $('<div class="alert alert-success alert-dismissible fade show" role="alert">')
                        .text('Community-specific content generated successfully.')
                        .append('<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>')
                        .insertAfter(btn.parent())
                        .delay(5000)
                        .fadeOut(function () { $(this).remove(); });
                },
                error: function (xhr) {
                    btn.prop('disabled', false).text('Generate Community-Specific Content');

                    // Check if we have a JSON error response
                    let errorMsg = 'Failed to generate community content.';
                    try {
                        const errorObj = JSON.parse(xhr.responseText);
                        if (errorObj.error) {
                            errorMsg = errorObj.error;
                        }
                    } catch (e) {
                        console.error('Error parsing error response:', e);
                    }

                    $('#community-generation-error')
                        .html(`<div class="alert alert-danger">
                        <strong>Error:</strong> ${errorMsg}
                    </div>`)
                        .show();
                }
            });
        });

        // Save community article changes
        $(document).on('click', '#save-community-article-btn', function () {
            const btn = $(this);
            const articleTitle = $('#community-article-title').val().trim();
            const articleContent = $('#community-article-content').val().trim();

            btn.prop('disabled', true).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Saving...');

            $.ajax({
                url: '/community_articles/save_content',
                method: 'POST',
                data: {
                    article_title: articleTitle,
                    article_content: articleContent
                },
                success: function (response) {
                    btn.prop('disabled', false).text('Save Changes');

                    if (response.error) {
                        alert('Error: ' + response.error);
                        return;
                    }

                    // Show success message
                    $('<div class="alert alert-success alert-dismissible fade show" role="alert">')
                        .text('Community article saved successfully.')
                        .append('<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>')
                        .insertAfter(btn.parent());
                },
                error: function (xhr) {
                    btn.prop('disabled', false).text('Save Changes');
                    alert('Failed to save community article: ' + xhr.responseText);
                }
            });
        });

        // Handle article selection change - reload community articles
        $('#article-select').change(function () {
            if ($('#community-articles-list').length > 0) {
                loadCommunityArticles();
            }
        });

        // Auto-save functionality for community article content
        let communityAutoSaveTimeout;
        $(document).on('input', '#community-article-title, #community-article-content', function () {
            clearTimeout(communityAutoSaveTimeout);
            communityAutoSaveTimeout = setTimeout(function () {
                $('#save-community-article-btn').click();
            }, 3000); // Auto-save after 3 seconds of inactivity
        });
    });

    // Auto-save functionality for fields in the final article section
    let autoSaveTimeout;
    $(document).on('input', '#final-article-title, #final-article-content, #final-meta-title, #final-meta-desc', function () {
        clearTimeout(autoSaveTimeout);
        autoSaveTimeout = setTimeout(function () {
            $('#save-final-article-btn').click();
        }, 3000); // Auto-save after 3 seconds of inactivity
    });

    // --- Dynamic Primary Content Category Dropdown ---
    const journeyToCategories = {
        'Awareness & Research': [
            'Affordability & Pricing',
            'Planning Ahead',
            'Caregiver Education'
        ],
        'Consideration': [
            'Affordability & Pricing',
            'Healthcare',
            'Senior Living Features & Services',
            'Dining & Nutrition',
            'Safety & Security',
            'Lifestyle'
        ],
        'Evaluation & Residency': [
            'Affordability & Pricing',
            'Lifestyle',
            'Innovation',
            'Resident & Family Experiences'
        ]
    };

    function updateCategoryOptions(selectedStage, selectedCategory) {
        const $category = $('#category');
        $category.empty();
        if (selectedStage && journeyToCategories[selectedStage]) {
            journeyToCategories[selectedStage].forEach(cat => {
                const isSelected = selectedCategory && selectedCategory === cat ? 'selected' : '';
                $category.append(`<option value="${cat}" ${isSelected}>${cat}</option>`);
            });
        }
    }

    $(document).ready(function() {
        // On page load, set the category options based on the current journey stage
        const $journeyStage = $('#journey-stage');
        const $category = $('#category');
        let initialStage = $journeyStage.val();
        let initialCategory = $category.data('selected'); // for update form, if needed
        updateCategoryOptions(initialStage, initialCategory);

        $journeyStage.on('change', function() {
            updateCategoryOptions($(this).val(), null);
        });
    });
});

