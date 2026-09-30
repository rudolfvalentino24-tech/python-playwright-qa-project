def apply_jira_modal_error_fix(ui_redesign):
    """Show Jira API/configuration errors inside the redesigned Jira modal."""
    template = ui_redesign.MAIN_PAGE_HTML

    template = template.replace(
        "let jiraStories=[];const jiraBrowseBase=",
        "let jiraStories=[];let jiraStoriesError='';const jiraBrowseBase=",
        1,
    )

    old_render = "function renderJiraModalStories(prefix){const list=document.getElementById(prefix+'JiraModalList');const search=document.getElementById(prefix+'JiraModalSearch').value.trim().toLowerCase();const selected=jiraModalSelections[prefix]||new Set();const matches=jiraStories.filter(story=>!search||story.key.toLowerCase().includes(search)||story.summary.toLowerCase().includes(search));if(!matches.length){list.innerHTML='<div class=\"jira-modal-message\">No matching Jira tickets.</div>';return;}"
    new_render = "function renderJiraModalStories(prefix){const list=document.getElementById(prefix+'JiraModalList');if(jiraStoriesError){list.innerHTML='<div class=\"jira-modal-message\" style=\"color:#b42318;font-weight:750\">'+escapeHtml(jiraStoriesError)+'</div>';return;}const search=document.getElementById(prefix+'JiraModalSearch').value.trim().toLowerCase();const selected=jiraModalSelections[prefix]||new Set();const matches=jiraStories.filter(story=>!search||story.key.toLowerCase().includes(search)||story.summary.toLowerCase().includes(search));if(!matches.length){list.innerHTML='<div class=\"jira-modal-message\">No matching Jira tickets.</div>';return;}"
    template = template.replace(old_render, new_render, 1)

    old_load = "async function loadJiraStories(prefix){try{const response=await fetch('/api/jira/stories');const data=await response.json();if(!response.ok)throw new Error(data.error||'Unable to load Jira stories.');jiraStories=data.stories||[];renderSelectedJiraStories(prefix);}catch(error){const container=document.getElementById(prefix+'SelectedJiraStories');if(container)container.innerHTML='<div class=\"jira-selected-empty\">'+escapeHtml(error.message)+'</div>';}}"
    new_load = "async function loadJiraStories(prefix){try{const response=await fetch('/api/jira/stories');const data=await response.json();if(!response.ok)throw new Error(data.error||'Unable to load Jira stories.');jiraStoriesError='';jiraStories=data.stories||[];renderSelectedJiraStories(prefix);}catch(error){jiraStories=[];jiraStoriesError=error.message||'Unable to load Jira stories.';const container=document.getElementById(prefix+'SelectedJiraStories');if(container)container.innerHTML='<div class=\"jira-selected-empty\">'+escapeHtml(jiraStoriesError)+'</div>';}}"
    template = template.replace(old_load, new_load, 1)

    ui_redesign.MAIN_PAGE_HTML = template
