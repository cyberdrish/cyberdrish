import argparse
import html
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


class ContributionCalendar(HTMLParser):
    def __init__(self):
        super().__init__()
        self.days = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'data-date' in attrs and 'data-level' in attrs:
            day = date.fromisoformat(attrs['data-date'])
            level = int(attrs['data-level'])
            if not 0 <= level <= 4:
                raise ValueError('Unexpected contribution level')
            self.days[day] = level


def render(days, username):
    if not 350 <= len(days) <= 371:
        raise ValueError(f'Incomplete contribution calendar: {len(days)} days')
    first, last = min(days), max(days)
    if (last - first).days + 1 != len(days):
        raise ValueError('Contribution calendar contains missing dates')
    start = first - timedelta(days=(first.weekday() + 1) % 7)
    columns = (last - start).days // 7 + 1
    pitch, x0, y0 = 16, 48, 66
    width, height = x0 + columns * pitch + 28, 224
    palette = ['#161B22', '#312E81', '#5B21B6', '#8B5CF6', '#C4B5FD']
    route = [(col, row) for col in range(columns)
             for row in (range(7) if col % 2 == 0 else range(6, -1, -1))]
    positions = {cell: index for index, cell in enumerate(route)}
    distance = len(route) - 1
    path = ' '.join(f'{"M" if i == 0 else "L"}{x0 + col*pitch + 5.5},{y0 + row*pitch + 5.5}'
                    for i, (col, row) in enumerate(route))
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
             f'<title id="title">{html.escape(username)} contribution snake</title>',
             f'<desc id="desc">Public GitHub contribution intensity from {first} to {last}. A violet snake traverses the calendar. Colors represent GitHub contribution levels, not individual contribution counts.</desc>',
             '<style>.snake{animation:travel 32s linear infinite}.day{animation-duration:32s;animation-timing-function:linear;animation-iteration-count:infinite}',
             '@keyframes travel{from{stroke-dashoffset:5}to{stroke-dashoffset:%d}}' % (-distance-5),
             '@media(prefers-reduced-motion:reduce){.snake{display:none}.day{animation:none!important}}']
    for day, level in sorted(days.items()):
        delta = (day - start).days
        col, row = delta // 7, delta % 7
        eaten = (positions[(col, row)] + 5) / (distance + 10) * 100
        if level:
            parts.append(f'@keyframes d{delta}{{0%,{max(0, eaten-0.02):.3f}%{{opacity:1}}{eaten:.3f}%,98%{{opacity:0}}100%{{opacity:1}}}}')
    parts.extend(['</style>',
                  f'<rect x="0.5" y="0.5" width="{width-1}" height="{height-1}" rx="12" fill="#0D1117" stroke="#312E81"/>',
                  '<g font-family="Segoe UI,Arial,sans-serif">',
                  '<text x="28" y="30" fill="#C4B5FD" font-size="15" font-weight="600">Contribution Calendar</text>',
                  f'<text x="{width-28}" y="30" text-anchor="end" fill="#8B949E" font-size="10">{first} — {last}</text>'])
    months = set()
    for day, level in sorted(days.items()):
        delta = (day-start).days
        col, row = delta // 7, delta % 7
        x, y = x0 + col*pitch, y0 + row*pitch
        month = (day.year, day.month)
        if month not in months:
            if not months or day.day == 1:
                parts.append(f'<text x="{x}" y="55" fill="#8B949E" font-size="10">{day:%b}</text>')
            months.add(month)
        parts.append(f'<rect x="{x}" y="{y}" width="11" height="11" rx="2" fill="{palette[0]}"/>')
        if level:
            parts.append(f'<rect class="day" style="animation-name:d{delta}" x="{x}" y="{y}" width="11" height="11" rx="2" fill="{palette[level]}"><title>{day}: contribution level {level} of 4</title></rect>')
    for row, name in [(1, 'Mon'), (3, 'Wed'), (5, 'Fri')]:
        parts.append(f'<text x="15" y="{y0 + row*pitch+9}" fill="#8B949E" font-size="9">{name}</text>')
    parts.append(f'<path class="snake" d="{path}" pathLength="{distance}" fill="none" stroke="#A78BFA" stroke-width="9" stroke-linecap="round" stroke-linejoin="round" stroke-dasharray="5 {distance+10}" stroke-dashoffset="5"/>')
    parts.append('<text x="28" y="204" fill="#8B949E" font-size="10">Public contribution activity · cyberdrish</text>')
    parts.append(f'<text x="{width-160}" y="204" fill="#8B949E" font-size="10">Less</text>')
    for i, color in enumerate(palette):
        parts.append(f'<rect x="{width-130+i*15}" y="195" width="11" height="11" rx="2" fill="{color}"/>')
    parts.append(f'<text x="{width-48}" y="204" fill="#8B949E" font-size="10">More</text>')
    parts.append('</g></svg>')
    return '\n'.join(parts) + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--username', default='cyberdrish')
    parser.add_argument('--input', type=Path)
    parser.add_argument('--output', type=Path, default=Path('assets/github-contribution-snake.svg'))
    args = parser.parse_args()
    if args.input:
        source = args.input.read_text(encoding='utf-8')
    else:
        if not args.username or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-' for c in args.username):
            raise ValueError('Invalid GitHub username')
        request = Request(f'https://github.com/users/{args.username}/contributions',
                          headers={'User-Agent': 'cyberdrish-profile-calendar', 'Accept': 'text/html'})
        with urlopen(request, timeout=30) as response:
            source = response.read().decode('utf-8')
    calendar = ContributionCalendar()
    calendar.feed(source)
    svg = render(calendar.days, args.username)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix('.tmp')
    temporary.write_text(svg, encoding='utf-8')
    temporary.replace(args.output)
    print(f'Generated {args.output} from {len(calendar.days)} contribution days.')


if __name__ == '__main__':
    main()
