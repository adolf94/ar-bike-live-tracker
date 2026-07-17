import dayjs from 'dayjs';

export function formatDisplayDate(isoDate: string): string {
  const date = dayjs(isoDate);
  const now = dayjs();

  if (date.isSame(now, 'day')) {
    return date.format('h:mm a');
  }

  if (date.isSame(now.subtract(1, 'day'), 'day')) {
    return `Yesterday, ${date.format('h:mm a')}`;
  }

  return date.format('MMM D, h:mm a');
}

export function formatEventTime(isoDate: string): string {
  const date = dayjs(isoDate);
  const now = dayjs();

  if (date.isSame(now, 'day')) {
    return date.format('h:mm:ss a');
  }

  if (date.isSame(now.subtract(1, 'day'), 'day')) {
    return `Yesterday, ${date.format('h:mm:ss a')}`;
  }

  return date.format('MMM D, h:mm:ss a');
}