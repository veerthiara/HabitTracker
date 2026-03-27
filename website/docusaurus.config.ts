import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const repoName = process.env.GITHUB_REPOSITORY?.split('/')[1] ?? 'HabitTracker';
const isGitHubPages = process.env.GITHUB_ACTIONS === 'true';

const config: Config = {
  title: 'HabitTracker Docs',
  tagline: 'Roadmap, implementation notes, and architecture in reading order.',
  url: 'https://veerthiara.github.io',
  baseUrl: isGitHubPages ? `/${repoName}/` : '/',
  organizationName: 'veerthiara',
  projectName: repoName,
  trailingSlash: false,
  onBrokenLinks: 'throw',
  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },
  presets: [
    [
      'classic',
      {
        docs: {
          path: '../docs',
          routeBasePath: '/',
          sidebarPath: './sidebars.ts',
          editUrl:
            'https://github.com/veerthiara/HabitTracker/tree/main/',
        },
        blog: false,
        pages: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],
  themeConfig: {
    navbar: {
      title: 'HabitTracker Docs',
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docs',
          position: 'left',
          label: 'Read the Docs',
        },
        {
          href: 'https://github.com/veerthiara/HabitTracker',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Docs',
          items: [
            {
              label: 'Start Here',
              to: '/',
            },
            {
              label: 'Roadmap',
              to: '/category/roadmap',
            },
            {
              label: 'Implementation',
              to: '/category/implementation',
            },
          ],
        },
        {
          title: 'Project',
          items: [
            {
              label: 'Repository',
              href: 'https://github.com/veerthiara/HabitTracker',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} HabitTracker`,
    },
    docs: {
      sidebar: {
        autoCollapseCategories: false,
      },
    },
    colorMode: {
      disableSwitch: true,
      defaultMode: 'light',
    },
    prism: {
      additionalLanguages: ['bash', 'python', 'yaml'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
