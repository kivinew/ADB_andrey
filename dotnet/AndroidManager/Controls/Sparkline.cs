using Avalonia;
using Avalonia.Controls;
using Avalonia.Media;
using Avalonia.Styling;

namespace AndroidManager.Controls;

/// <summary>График значений: линия по последним замерам. Рисуется на GPU, без вьюшки на точку.</summary>
public sealed class Sparkline : Control
{
    static Sparkline()
    {
        AffectsRender<Sparkline>(ValuesProperty, MaxProperty, LineBrushProperty);
    }

    public static readonly StyledProperty<IList<double>?> ValuesProperty =
        AvaloniaProperty.Register<Sparkline, IList<double>?>(nameof(Values));

    /// <summary>Верхняя граница шкалы. 0 — линия по середине (шкалы нет).</summary>
    public static readonly StyledProperty<double> MaxProperty =
        AvaloniaProperty.Register<Sparkline, double>(nameof(Max), 100);

    public static readonly StyledProperty<IBrush?> LineBrushProperty =
        AvaloniaProperty.Register<Sparkline, IBrush?>(nameof(LineBrush));

    public IList<double>? Values
    {
        get => GetValue(ValuesProperty);
        set => SetValue(ValuesProperty, value);
    }

    public double Max
    {
        get => GetValue(MaxProperty);
        set => SetValue(MaxProperty, value);
    }

    public IBrush? LineBrush
    {
        get => GetValue(LineBrushProperty);
        set => SetValue(LineBrushProperty, value);
    }

    public override void Render(DrawingContext context)
    {
        var values = Values;
        var width = Bounds.Width;
        var height = Bounds.Height;

        if (values is null || values.Count < 2 || width <= 1 || height <= 1)
            return;

        var max = Max > 0 ? Max : 0;
        var step = width / (values.Count - 1);
        var pen = new Pen(LineBrush ?? Brushes.Transparent, 1.5);

        var prev = PointAt(values[0], max, height, 0);

        for (var i = 1; i < values.Count; i++)
        {
            var cur = PointAt(values[i], max, height, step * i);
            context.DrawLine(pen, prev, cur);
            prev = cur;
        }
    }

    private static Point PointAt(double value, double max, double height, double x)
    {
        var t = max > 0 ? Math.Clamp(value / max, 0, 1) : 0.5;
        return new Point(x, height - t * height);
    }
}