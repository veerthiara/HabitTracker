import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docs: [
    'intro',
    {
      type: 'category',
      label: 'Roadmap',
      link: {
        type: 'generated-index',
        title: 'Roadmap',
        description: 'Read the product plan phase by phase.',
      },
      items: [
        'roadmap/project-plan',
        'roadmap/phase-01-bootstrap',
        'roadmap/phase-02-core-db',
        'roadmap/phase-03-manual-mvp',
        'roadmap/phase-04-pgvector',
        'roadmap/phase-04-pgvector-detailed',
        'roadmap/phase-05-ai-chat',
        'roadmap/phase-05-ai-chat-detailed',
        'roadmap/phase-06-langgraph',
        'roadmap/phase-06-langgraph-detailed',
        'roadmap/phase-07-ui-polish',
        'roadmap/phase-08-vision-foundation',
      ],
    },
    {
      type: 'category',
      label: 'Implementation',
      link: {
        type: 'generated-index',
        title: 'Implementation',
        description: 'Track phase-by-phase implementation revisions.',
      },
      items: [
        'implementation/phase-02-rev01',
        'implementation/phase-02-rev02',
        'implementation/phase-02-rev03',
        'implementation/phase-03-rev01',
        'implementation/phase-03-rev02',
        'implementation/phase-03-rev03',
        'implementation/phase-03-rev04',
        'implementation/phase-04-rev01',
        'implementation/phase-04-rev02',
        'implementation/phase-04-rev03',
        'implementation/phase-04-rev04',
        'implementation/phase-05-rev01',
        'implementation/phase-05-rev02',
        'implementation/phase-05-rev03',
        'implementation/phase-05-rev04',
        'implementation/phase-06-rev01',
        'implementation/phase-06-rev02',
        'implementation/phase-06-rev03',
      ],
    },
    {
      type: 'category',
      label: 'Architecture',
      link: {
        type: 'generated-index',
        title: 'Architecture',
        description: 'High-level system design and data model references.',
      },
      items: ['architecture/system-overview', 'architecture/data-model'],
    },
    {
      type: 'category',
      label: 'Copilot',
      link: {
        type: 'generated-index',
        title: 'Copilot Prompts',
        description: 'Repo-specific prompts and working rules.',
      },
      items: ['copilot/prompts'],
    },
  ],
};

export default sidebars;
