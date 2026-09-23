// Shared by the match page and the new-match form.
window.OsuTeamCreator = class OsuTeamCreator {
    constructor(root, onCreate) {
        this.root = root;
        this.onCreate = onCreate;
        this.button = root.querySelector('[data-create-team]');
        this.message = root.querySelector('[data-team-message]');
        this.button.addEventListener('click', () => this.create());
        root.addEventListener('keydown', event => {
            if (event.key === 'Enter' && event.target.matches('input')) {
                event.preventDefault();
                this.create();
            }
        });
    }

    field(name) {
        return this.root.querySelector(`[data-team-field="${name}"]`);
    }

    async create() {
        if (this.button.disabled) return;
        const team = {
            name: this.field('name').value.trim(),
            acronym: this.field('acronym').value.trim().toUpperCase(),
            color: this.field('color').value
        };
        this.message.textContent = '';
        if (!team.name || !team.acronym || team.acronym.length > 4) {
            this.message.textContent = 'Enter a name and an acronym of 1–4 characters.';
            return;
        }
        this.button.disabled = true;
        try {
            await this.onCreate(team);
            this.field('name').value = '';
            this.field('acronym').value = '';
            this.field('color').value = '#808080';
            this.message.textContent = `Added ${team.name}.`;
        } catch (error) {
            this.message.textContent = error.message || 'Could not create team. Please try again.';
        } finally {
            this.button.disabled = false;
        }
    }
};
