#!/usr/bin/env python
import os
import json

if 'DISPLAY' not in os.environ:
    import matplotlib
    matplotlib.use('agg')

import glob
import pandas as pd
import click
import pickle
from typing import List
import numpy as np
from plotnine import (
    ggplot, aes, facet_wrap,
    geom_smooth, geom_density, geom_histogram, geom_bar, geom_line,
    coord_flip, stat_smooth, scale_y_continuous, scale_x_continuous,
    xlab, ylab, theme
)


QB_ROOT = os.environ.get('QB_ROOT', '')
DEV_REPORT_PATTERN = os.path.join(QB_ROOT, 'output/guesser/**/0/guesser_report_guessdev.pickle')
TEST_REPORT_PATTERN = os.path.join(QB_ROOT, 'output/guesser/**/0/guesser_report_guesstest.pickle')
EXPO_REPORT_PATTERN = os.path.join(QB_ROOT, 'output/guesser/**/0/guesser_report_expo.pickle')


@click.group()
def main():
    pass


def safe_path(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def category_jmlr(cat):
    if cat in {'Religion', 'Myth', 'Philosophy'}:
        return 'Religion/Myth/Philosophy'
    elif cat == 'Trash':
        return 'Popular Culture'
    else:
        return cat


def int_to_correct(num):
    if num == 1:
        return 'Correct'
    else:
        return 'Wrong'


def save_plot(output_dir, guesser_name, name, plot, width=None, height=None):
    plot.save(safe_path(os.path.join(output_dir, guesser_name, name)), width=width, height=height)


class GuesserReport:
    def __init__(self, unpickled_report, fold):
        self.fold = fold
        self.char_df = unpickled_report['char_df']
        self.first_df = unpickled_report['first_df']
        self.full_df = unpickled_report['full_df']
        self.guesser_name = unpickled_report['guesser_name']

        self.full_df['seen'] = 'Full Question'
        self.first_df['seen'] = 'First Sentence'
        self.combined_df = pd.concat([self.full_df, self.first_df])
        self.combined_df['Outcome'] = self.combined_df.correct.map(int_to_correct)
        self.combined_df['category_jmlr'] = self.combined_df.category.map(category_jmlr)
        self.combined_df = self.combined_df.groupby(['qanta_id', 'seen']).nth(0).reset_index()

        self.char_plot_df = self.char_df\
            .sort_values('score', ascending=False)\
            .groupby(['qanta_id', 'char_index'])\
            .nth(0).reset_index()
        self.char_plot_df['category_jmlr'] = self.char_plot_df.category.map(category_jmlr)
        self.char_plot_df['Outcome'] = self.char_plot_df.correct.map(int_to_correct)
        self.first_accuracy = unpickled_report['first_accuracy']
        self.full_accuracy = unpickled_report['full_accuracy']
        self.unanswerable_answer_percent = unpickled_report['unanswerable_answer_percent']
        self.unanswerable_question_percent = unpickled_report['unanswerable_question_percent']

    def plot_n_train_vs_accuracy(self):
        return (
            ggplot(self.combined_df) + facet_wrap('seen')
            + aes(x='n_train', fill='Outcome')
            + geom_histogram(binwidth=1)
        )

    def plot_char_percent_vs_accuracy_histogram(self, category=False):
        if category:
            return (
                ggplot(self.char_plot_df) + facet_wrap('category_jmlr')
                + aes(x='char_percent', fill='Outcome')
                + geom_histogram(binwidth=.05)
            )
        else:
            return (
                ggplot(self.char_plot_df)
                + aes(x='char_percent', fill='Outcome')
                + geom_histogram(binwidth=.05)
            )

    def plot_char_percent_vs_accuracy_smooth(self, category=False):
        if category:
            return (
                ggplot(self.char_plot_df)
                + aes(x='char_percent', y='correct', color='category_jmlr')
                + geom_smooth()
            )
        else:
            return (
                    ggplot(self.char_plot_df)
                    + aes(x='char_percent', y='correct')
                    + geom_smooth(method='mavg')
            )


GUESSER_SHORT_NAMES = {
    'qanta.guesser.rnn.RnnGuesser': 'RNN',
    'qanta.guesser.dan.DanGuesser': 'DAN',
    'qanta.guesser.elasticsearch.ElasticSearchGuesser': 'IR'
}


def to_shortname(name):
    if name in GUESSER_SHORT_NAMES:
        return GUESSER_SHORT_NAMES[name]
    else:
        return name


def to_dataset(fold):
    if fold == 'expo':
        return 'Challenge Questions'
    elif fold == 'guesstest':
        return 'Test Questions'
    else:
        return fold

class CompareGuesserReport:
    def __init__(self, reports: List[GuesserReport]):
        self.reports = reports
        char_plot_dfs = []
        acc_rows = []
        for r in self.reports:
            char_plot_dfs.append(r.char_plot_df)
            name = to_shortname(r.guesser_name)
            dataset = to_dataset(r.fold)
            acc_rows.append((r.fold, name, 'First Sentence', r.first_accuracy, dataset))
            acc_rows.append((r.fold, name, 'Full Question', r.full_accuracy, dataset))
        self.char_plot_df = pd.concat(char_plot_dfs)
        self.char_plot_df['Guessing_Model'] = self.char_plot_df['guesser'].map(to_shortname)
        self.char_plot_df['Dataset'] = self.char_plot_df['fold'].map(to_dataset)
        self.acc_df = pd.DataFrame.from_records(acc_rows, columns=['fold', 'guesser', 'position', 'accuracy', 'Dataset'])

    def plot_char_percent_vs_accuracy_smooth(self, expo=False):
        if expo:
            p = (
                ggplot(self.char_plot_df) + facet_wrap('Guessing_Model', nrow=1)
                + aes(x='char_percent', y='correct', color='Dataset')
                + stat_smooth(method='mavg', se=False, method_args={'window': 200})
                + scale_y_continuous(breaks=np.linspace(0, 1, 11))
                + scale_x_continuous(breaks=[0, .5, 1])
                + xlab('Percent of Question Revealed')
                + ylab('Accuracy')
                + theme(legend_position='top')
            )
            if os.path.exists('data/external/human_gameplay.json'):
                with open('data/external/human_gameplay.json') as f:
                    gameplay = json.load(f)
                    control_correct_positions = gameplay['control_correct_positions']
                    control_wrong_positions = gameplay['control_wrong_positions']
                    control_positions = control_correct_positions + control_wrong_positions
                    control_positions = np.array(control_positions)
                    control_result = np.array(len(control_correct_positions) * [1] + len(control_wrong_positions) * [0])
                    argsort_control = np.argsort(control_positions)
                    control_x = control_positions[argsort_control]
                    control_sorted_result = control_result[argsort_control]
                    control_y = control_sorted_result.cumsum() / control_sorted_result.shape[0]
                    control_df = pd.DataFrame({'correct': control_y, 'char_percent': control_x})
                    control_df['Dataset'] = 'Test Questions'
                    control_df['Guessing_Model'] = ' Human'

                    adv_correct_positions = gameplay['adv_correct_positions']
                    adv_wrong_positions = gameplay['adv_wrong_positions']
                    adv_positions = adv_correct_positions + adv_wrong_positions
                    adv_positions = np.array(control_positions)
                    adv_result = np.array(len(adv_correct_positions) * [1] + len(adv_wrong_positions) * [0])
                    argsort_adv = np.argsort(adv_positions)
                    adv_x = adv_positions[argsort_adv]
                    adv_sorted_result = adv_result[argsort_adv]
                    adv_y = adv_sorted_result.cumsum() / adv_sorted_result.shape[0]
                    adv_df = pd.DataFrame({'correct': adv_y, 'char_percent': adv_x})
                    adv_df['Dataset'] = 'Challenge Questions'
                    adv_df['Guessing_Model'] = ' Human'

                    human_df = pd.concat([control_df, adv_df])
                    p = p + (
                        geom_line(data=human_df)
                    )

            return p
        else:
            return (
                ggplot(self.char_plot_df)
                + aes(x='char_percent', y='correct', color='Guessing_Model')
                + stat_smooth(method='mavg', se=False, method_args={'window': 500})
                + scale_y_continuous(breaks=np.linspace(0, 1, 21))
            )

    def plot_compare_accuracy(self, expo=False):
        if expo:
            return (
                ggplot(self.acc_df) + facet_wrap('position')
                + aes(x='guesser', y='accuracy', fill='Dataset')
                + geom_bar(stat='identity', position='dodge')
                + xlab('Guessing Model')
                + ylab('Accuracy')
            )
        else:
            return (
                ggplot(self.acc_df) + facet_wrap('position')
                + aes(x='guesser', y='accuracy')
                + geom_bar(stat='identity')
            )


def save_all_plots(output_dir, report: GuesserReport, expo=False):
    if not expo:
        save_plot(
            output_dir, report.guesser_name,
            'n_train_vs_accuracy.pdf', report.plot_n_train_vs_accuracy()
        )
    save_plot(
        output_dir, report.guesser_name,
        'char_percent_vs_accuracy_histogram.pdf', report.plot_char_percent_vs_accuracy_histogram(category=False)
    )

    if not expo:
        save_plot(
            output_dir, report.guesser_name,
            'char_percent_vs_accuracy_histogram_category.pdf',
            report.plot_char_percent_vs_accuracy_histogram(category=True)
        )
    save_plot(
        output_dir, report.guesser_name,
        'char_percent_vs_accuracy_smooth.pdf', report.plot_char_percent_vs_accuracy_smooth(category=False)
    )

    if not expo:
        save_plot(
            output_dir, report.guesser_name,
            'char_percent_vs_accuracy_smooth_category.pdf', report.plot_char_percent_vs_accuracy_smooth(category=True)
        )


@main.command()
@click.option('--use-test', is_flag=True, default=False)
@click.argument('output_dir')
def guesser(use_test, output_dir):
    if use_test:
        REPORT_PATTERN = TEST_REPORT_PATTERN
        report_fold = 'guesstest'
    else:
        REPORT_PATTERN = DEV_REPORT_PATTERN
        report_fold = 'guessdev'
    dev_reports = []
    for path in glob.glob(REPORT_PATTERN):
        with open(path, 'rb') as f:
            report = GuesserReport(pickle.load(f), report_fold)
            dev_reports.append(report)

        save_all_plots(output_dir, report)

    expo_reports = []
    expo_output_dir = safe_path(os.path.join(output_dir, 'expo'))
    for path in glob.glob(EXPO_REPORT_PATTERN):
        with open(path, 'rb') as f:
            report = GuesserReport(pickle.load(f), 'expo')
            expo_reports.append(report)

        save_all_plots(expo_output_dir, report, expo=True)

    compare_report = CompareGuesserReport(dev_reports)
    save_plot(
        output_dir, 'compare', 'position_accuracy.pdf',
        compare_report.plot_compare_accuracy()
    )
    save_plot(
        output_dir, 'compare', 'char_accuracy.pdf',
        compare_report.plot_char_percent_vs_accuracy_smooth()
    )

    if len(expo_reports) > 0:
        compare_report = CompareGuesserReport(dev_reports + expo_reports)
        save_plot(
            output_dir, 'compare', 'expo_position_accuracy.pdf',
            compare_report.plot_compare_accuracy(expo=True)
        )
        save_plot(
            output_dir, 'compare', 'expo_char_accuracy.pdf',
            compare_report.plot_char_percent_vs_accuracy_smooth(expo=True),
            height=2.0, width=6.4
        )


if __name__ == '__main__':
    main()
