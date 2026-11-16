using System.Reflection;
using AndroidManager.Core.Tests;
using Xunit;

// Раннер на случай, когда testhost не стартует (Access denied на OpenProcess родителя).
// Те же [Fact] из AndroidManager.Core.Tests, те же Assert — меняется только запуск.
var passed = 0;
var failed = 0;

foreach (var type in typeof(NumTests).Assembly.GetTypes().OrderBy(t => t.FullName))
{
    var methods = type
        .GetMethods(BindingFlags.Public | BindingFlags.Instance)
        .Where(m => m.GetCustomAttribute<FactAttribute>() is not null)
        .OrderBy(m => m.Name)
        .ToList();

    if (methods.Count == 0)
        continue;

    Console.WriteLine(type.Name);

    foreach (var method in methods)
    {
        try
        {
            method.Invoke(Activator.CreateInstance(type), null);
            passed++;
            Console.WriteLine($"  OK   {method.Name}");
        }
        catch (TargetInvocationException ex)
        {
            failed++;
            // Стек нужен: без него непонятно, упал тест или сам раннер.
            var inner = ex.InnerException;
            var where = inner is null ? "" : $"\n{inner.StackTrace}";
            Console.WriteLine($"  FAIL {method.Name}: {inner?.Message}{where}");
        }
    }
}

Console.WriteLine();
Console.WriteLine($"Итого: {passed} пройдено, {failed} провалено");
return failed == 0 ? 0 : 1;